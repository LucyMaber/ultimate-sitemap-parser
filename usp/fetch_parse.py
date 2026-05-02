from typing import TYPE_CHECKING
from usp.fetch_parse import AbstractXMLSitemapParser


class PagesXMLSitemapParser(AbstractXMLSitemapParser):
    """
    Pages XML sitemap parser.

    Patched to be tolerant of malformed sitemap rows, for example:
    - <loc> outside <url>
    - empty <loc>
    - <url> entries with no valid <loc>
    - image/video extension tags outside a page row

    Instead of raising and stopping the whole sitemap parse, malformed rows are
    logged and skipped.
    """

    class Image:
        """Data class for holding image data while parsing."""

        __slots__ = ["loc", "caption", "geo_location", "title", "license"]

        def __init__(self):
            self.loc = None
            self.caption = None
            self.geo_location = None
            self.title = None
            self.license = None

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL to be able to find unique ones
                    self.loc,
                )
            )

    class Page:
        """Simple data class for holding various properties for a single <url> entry while parsing."""

        __slots__ = [
            "url",
            "last_modified",
            "change_frequency",
            "priority",
            "news_title",
            "news_publish_date",
            "news_publication_name",
            "news_publication_language",
            "news_access",
            "news_genres",
            "news_keywords",
            "news_stock_tickers",
            "images",
            "videos",
            "alternates",
        ]

        def __init__(self):
            self.url = None
            self.last_modified = None
            self.change_frequency = None
            self.priority = None
            self.news_title = None
            self.news_publish_date = None
            self.news_publication_name = None
            self.news_publication_language = None
            self.news_access = None
            self.news_genres = None
            self.news_keywords = None
            self.news_stock_tickers = None
            self.images = []
            self.videos = []
            self.alternates = []

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL to be able to find unique ones
                    self.url,
                )
            )

        def page(self) -> SitemapPage | None:
            """Return constructed sitemap page if one has been completed, otherwise None."""

            # Required by the sitemap protocol, but malformed sitemaps sometimes omit it.
            # In that case, skip this row instead of crashing the whole parse.
            url = html_unescape_strip(self.url)
            if not url:
                log.warning("Skipping malformed <url> entry because URL is unset.")
                return None

            last_modified = html_unescape_strip(self.last_modified)
            if last_modified:
                last_modified = parse_iso8601_date(last_modified)

            change_frequency = html_unescape_strip(self.change_frequency)
            if change_frequency:
                change_frequency = change_frequency.lower()
                if SitemapPageChangeFrequency.has_value(change_frequency):
                    change_frequency = SitemapPageChangeFrequency(change_frequency)
                else:
                    log.warning("Invalid change frequency, defaulting to 'always'.")
                    change_frequency = SitemapPageChangeFrequency.ALWAYS
                assert isinstance(change_frequency, SitemapPageChangeFrequency)

            priority = html_unescape_strip(self.priority)
            if priority:
                try:
                    priority = Decimal(priority)

                    if priority < MIN_VALID_PRIORITY or priority > MAX_VALID_PRIORITY:
                        log.warning(f"Priority is not within 0 and 1: {priority}")
                        priority = SITEMAP_PAGE_DEFAULT_PRIORITY
                except InvalidOperation:
                    log.warning(f"Invalid priority: {priority}")
                    priority = SITEMAP_PAGE_DEFAULT_PRIORITY
            else:
                priority = SITEMAP_PAGE_DEFAULT_PRIORITY

            news_title = html_unescape_strip(self.news_title)

            news_publish_date = html_unescape_strip(self.news_publish_date)
            if news_publish_date:
                news_publish_date = parse_iso8601_date(date_string=news_publish_date)

            news_publication_name = html_unescape_strip(self.news_publication_name)
            news_publication_language = html_unescape_strip(
                self.news_publication_language
            )
            news_access = html_unescape_strip(self.news_access)

            news_genres = html_unescape_strip(self.news_genres)
            if news_genres:
                news_genres = [x.strip() for x in news_genres.split(",")]
            else:
                news_genres = []

            news_keywords = html_unescape_strip(self.news_keywords)
            if news_keywords:
                news_keywords = [x.strip() for x in news_keywords.split(",")]
            else:
                news_keywords = []

            news_stock_tickers = html_unescape_strip(self.news_stock_tickers)
            if news_stock_tickers:
                news_stock_tickers = [x.strip() for x in news_stock_tickers.split(",")]
            else:
                news_stock_tickers = []

            sitemap_news_story = None
            if news_title and news_publish_date:
                sitemap_news_story = SitemapNewsStory(
                    title=news_title,
                    publish_date=news_publish_date,
                    publication_name=news_publication_name,
                    publication_language=news_publication_language,
                    access=news_access,
                    genres=news_genres,
                    keywords=news_keywords,
                    stock_tickers=news_stock_tickers,
                )

            sitemap_images = None
            if len(self.images) > 0:
                sitemap_images = [
                    SitemapImage(
                        loc=image.loc,
                        caption=image.caption,
                        geo_location=image.geo_location,
                        title=image.title,
                        license_=image.license,
                    )
                    for image in self.images
                    if html_unescape_strip(image.loc)
                ]

                if len(sitemap_images) == 0:
                    sitemap_images = None

            sitemap_videos = None
            if len(self.videos) > 0:
                sitemap_videos = [video.video() for video in self.videos]
                sitemap_videos = [video for video in sitemap_videos if video]
                if len(sitemap_videos) == 0:
                    sitemap_videos = None

            alternates = None
            if len(self.alternates) > 0:
                alternates = self.alternates

            return SitemapPage(
                url=url,
                last_modified=last_modified,
                change_frequency=change_frequency,
                priority=priority,
                news_story=sitemap_news_story,
                images=sitemap_images,
                videos=sitemap_videos,
                alternates=alternates,
            )

    __slots__ = [
        "_current_page",
        "_pages",
        "_page_urls",
        "_current_image",
        "_current_video",
    ]

    def __init__(self, url: str):
        super().__init__(url=url)

        self._current_page = None
        self._pages = []
        self._page_urls = set()
        self._current_image = None
        self._current_video = None

    def _last_char_data_or_none(self, name: str) -> str | None:
        value = html_unescape_strip(self._last_char_data)
        if not value:
            log.warning(
                f"Empty character data at the end of <{name}> in sitemap {self._url}; ignoring."
            )
            return None
        return value

    def _finish_current_image(self) -> None:
        if not self._current_image:
            return

        if not self._current_page:
            log.warning(
                f"Skipping <image:image> outside <url> in sitemap {self._url}."
            )
            self._current_image = None
            return

        if html_unescape_strip(self._current_image.loc):
            self._current_page.images.append(self._current_image)
        else:
            log.warning(
                f"Skipping <image:image> without <image:loc> in sitemap {self._url}."
            )

        self._current_image = None

    def _finish_current_video(self) -> None:
        if not self._current_video:
            return

        if not self._current_page:
            log.warning(
                f"Skipping <video:video> outside <url> in sitemap {self._url}."
            )
            self._current_video = None
            return

        self._current_page.videos.append(self._current_video)
        self._current_video = None

    def _finish_current_page(self) -> None:
        if not self._current_page:
            return

        # Close any dangling extension elements first.
        self._finish_current_image()
        self._finish_current_video()

        page_url = html_unescape_strip(self._current_page.url)

        if not page_url:
            log.warning(
                f"Skipping malformed <url> entry without valid <loc> in sitemap {self._url}."
            )
            self._current_page = None
            return

        self._current_page.url = page_url

        if page_url not in self._page_urls:
            self._pages.append(self._current_page)
            self._page_urls.add(page_url)

        self._current_page = None

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        super().xml_element_start(name=name, attrs=attrs)

        if name == "sitemap:url":
            # If a previous <url> never closed properly, finish it defensively.
            if self._current_page:
                log.warning(
                    f"Starting a new <url> before the previous one closed in sitemap {self._url}; finishing previous row."
                )
                self._finish_current_page()

            self._current_page = self.Page()

        elif name == "image:image":
            if not self._current_page:
                log.warning(
                    f"Ignoring <image:image> outside <url> in sitemap {self._url}."
                )
                return

            if self._current_image:
                log.warning(
                    f"Starting a new <image:image> before the previous one closed in sitemap {self._url}; finishing previous image."
                )
                self._finish_current_image()

            self._current_image = self.Image()

        elif name == "video:video":
            if not self._current_page:
                log.warning(
                    f"Ignoring <video:video> outside <url> in sitemap {self._url}."
                )
                return

            if self._current_video:
                log.warning(
                    f"Starting a new <video:video> before the previous one closed in sitemap {self._url}; finishing previous video."
                )
                self._finish_current_video()

            self._current_video = _ParsedVideo()

        elif name == "video:restriction":
            if self._current_video:
                self._current_video.apply_restriction_attrs(attrs)

        elif name == "video:platform":
            if self._current_video:
                self._current_video.apply_platform_attrs(attrs)

        elif name == "video:uploader":
            if self._current_video:
                self._current_video.apply_uploader_attrs(attrs)

        elif name == "link":
            # XHTML alternate link extension.
            if not self._current_page:
                log.debug(f"Ignoring <link> outside <url> in sitemap {self._url}.")
                return

            if "rel" not in attrs or attrs["rel"] != "alternate":
                log.warning(f"<link> element is missing rel attribute: {attrs}.")
            elif "hreflang" not in attrs or "href" not in attrs:
                log.warning(
                    f"<link> element is missing hreflang or href attributes: {attrs}."
                )
            else:
                self._current_page.alternates.append((attrs["hreflang"], attrs["href"]))

    def xml_element_end(self, name: str) -> None:
        try:
            # Ignore stray end tags outside a <url> row instead of crashing.
            if not self._current_page:
                if name != "sitemap:urlset":
                    log.warning(
                        f"Ignoring </{name}> outside <url> in sitemap {self._url}."
                    )
                return

            if name == "sitemap:url":
                self._finish_current_page()

            elif name == "image:image":
                self._finish_current_image()

            elif name == "video:video":
                self._finish_current_video()

            else:
                if name == "sitemap:loc":
                    value = self._last_char_data_or_none(name)
                    if value:
                        self._current_page.url = value

                elif name == "sitemap:lastmod":
                    self._current_page.last_modified = self._last_char_data

                elif name == "sitemap:changefreq":
                    self._current_page.change_frequency = self._last_char_data

                elif name == "sitemap:priority":
                    self._current_page.priority = self._last_char_data

                elif name == "news:name":
                    self._current_page.news_publication_name = self._last_char_data

                elif name == "news:language":
                    self._current_page.news_publication_language = self._last_char_data

                elif name == "news:publication_date":
                    self._current_page.news_publish_date = self._last_char_data

                elif name == "news:title":
                    value = self._last_char_data_or_none(name)
                    if value:
                        self._current_page.news_title = value

                elif name == "news:access":
                    self._current_page.news_access = self._last_char_data

                elif name == "news:keywords":
                    self._current_page.news_keywords = self._last_char_data

                elif name == "news:stock_tickers":
                    self._current_page.news_stock_tickers = self._last_char_data

                elif name == "image:loc":
                    if self._current_image:
                        value = self._last_char_data_or_none(name)
                        if value:
                            self._current_image.loc = value
                    else:
                        log.warning(
                            f"Ignoring <image:loc> outside <image:image> in sitemap {self._url}."
                        )

                elif name == "image:caption":
                    if self._current_image:
                        self._current_image.caption = self._last_char_data

                elif name == "image:geo_location":
                    if self._current_image:
                        self._current_image.geo_location = self._last_char_data

                elif name == "image:title":
                    if self._current_image:
                        self._current_image.title = self._last_char_data

                elif name == "image:license":
                    if self._current_image:
                        self._current_image.license = self._last_char_data

                elif self._current_video:
                    if name == "video:thumbnail_loc":
                        value = self._last_char_data_or_none(name)
                        if value:
                            self._current_video.thumbnail_loc = value

                    elif name == "video:title":
                        value = self._last_char_data_or_none(name)
                        if value:
                            self._current_video.title = value

                    elif name == "video:description":
                        value = self._last_char_data_or_none(name)
                        if value:
                            self._current_video.description = value

                    elif name == "video:content_loc":
                        self._current_video.content_loc = self._last_char_data

                    elif name == "video:player_loc":
                        self._current_video.player_loc = self._last_char_data

                    elif name == "video:duration":
                        self._current_video.duration = self._last_char_data

                    elif name == "video:expiration_date":
                        self._current_video.expiration_date = self._last_char_data

                    elif name == "video:rating":
                        self._current_video.rating = self._last_char_data

                    elif name == "video:view_count":
                        self._current_video.view_count = self._last_char_data

                    elif name == "video:publication_date":
                        self._current_video.publication_date = self._last_char_data

                    elif name == "video:family_friendly":
                        self._current_video.family_friendly = self._last_char_data

                    elif name == "video:restriction":
                        self._current_video.restriction_values = self._last_char_data

                    elif name == "video:platform":
                        self._current_video.platform_values = self._last_char_data

                    elif name == "video:requires_subscription":
                        self._current_video.requires_subscription = self._last_char_data

                    elif name == "video:uploader":
                        self._current_video.uploader = self._last_char_data

                    elif name == "video:live":
                        self._current_video.live = self._last_char_data

                    elif name == "video:tag":
                        self._current_video.add_tag(self._last_char_data)

        finally:
            super().xml_element_end(name=name)

    def sitemap(self) -> AbstractSitemap:
        # If the XML ended while a <url> was still open, keep any usable data.
        if self._current_page:
            log.warning(
                f"Sitemap {self._url} ended while a <url> entry was still open; finishing row."
            )
            self._finish_current_page()

        pages = []

        for page_row in self._pages:
            page = page_row.page()
            if page:
                pages.append(page)

        pages_sitemap = PagesXMLSitemap(url=self._url, pages=pages)

        return pages_sitemap