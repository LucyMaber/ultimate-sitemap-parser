"""Objects that represent a page found in one of the sitemaps."""

import datetime
from decimal import Decimal
from enum import Enum, unique

SITEMAP_PAGE_DEFAULT_PRIORITY = Decimal("0.5")
"""Default sitemap page priority, as per the spec."""


class SitemapNewsStory:
    """
    Single story derived from Google News XML sitemap.
    """

    __slots__ = [
        "__title",
        "__publish_date",
        "__publication_name",
        "__publication_language",
        "__access",
        "__genres",
        "__keywords",
        "__stock_tickers",
    ]

    def __init__(
        self,
        title: str,
        publish_date: datetime.datetime,
        publication_name: str | None = None,
        publication_language: str | None = None,
        access: str | None = None,
        genres: list[str] | None = None,
        keywords: list[str] | None = None,
        stock_tickers: list[str] | None = None,
    ):
        """
        Initialize a new Google News story.

        :param title: Story title.
        :param publish_date: Story publication date.
        :param publication_name: Name of the news publication in which the article appears in.
        :param publication_language: Primary language of the news publication in which the article appears in.
        :param access: Accessibility of the article.
        :param genres: List of properties characterizing the content of the article.
        :param keywords: List of keywords describing the topic of the article.
        :param stock_tickers: List of up to 5 stock tickers that are the main subject of the article.
        """

        # Spec defines that some of the properties below are "required" but in practice not every website provides the
        # required properties. So, we require only "title" and "publish_date" to be set.

        self.__title = title
        self.__publish_date = publish_date
        self.__publication_name = publication_name
        self.__publication_language = publication_language
        self.__access = access
        self.__genres = genres if genres else []
        self.__keywords = keywords if keywords else []
        self.__stock_tickers = stock_tickers if stock_tickers else []

    def __eq__(self, other) -> bool:
        """Check equality."""
        if not isinstance(other, SitemapNewsStory):
            raise NotImplementedError

        if self.title != other.title:
            return False

        if self.publish_date != other.publish_date:
            return False

        if self.publication_name != other.publication_name:
            return False

        if self.publication_language != other.publication_language:
            return False

        if self.access != other.access:
            return False

        if self.genres != other.genres:
            return False

        if self.keywords != other.keywords:
            return False

        if self.stock_tickers != other.stock_tickers:
            return False

        return True

    def to_dict(self) -> dict:
        """
        Convert to a dictionary representation.

        :return: the news story data as a dictionary
        """
        return {
            "title": self.title,
            "publish_date": self.publish_date,
            "publication_name": self.publication_name,
            "publication_language": self.publication_language,
            "access": self.access,
            "genres": self.genres,
            "keywords": self.keywords,
            "stock_tickers": self.stock_tickers,
        }

    def __hash__(self):
        return hash(
            (
                self.title,
                self.publish_date,
                self.publication_name,
                self.publication_language,
                self.access,
                tuple(self.genres),
                tuple(self.keywords),
                tuple(self.stock_tickers),
            )
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"title={self.title}, "
            f"publish_date={self.publish_date}, "
            f"publication_name={self.publication_name}, "
            f"publication_language={self.publication_language}, "
            f"access={self.access}, "
            f"genres={self.genres}, "
            f"keywords={self.keywords}, "
            f"stock_tickers={self.stock_tickers}"
            ")"
        )

    @property
    def title(self) -> str:
        """Get the story title."""
        return self.__title

    @property
    def publish_date(self) -> datetime.datetime:
        """Get the  story publication date."""
        return self.__publish_date

    @property
    def publication_name(self) -> str | None:
        """Get the name of the news publication in which the article appears."""
        return self.__publication_name

    @property
    def publication_language(self) -> str | None:
        """Get the primary language of the news publication in which the article appears.

        It should be an ISO 639 Language Code (either 2 or 3 letters).
        """
        return self.__publication_language

    @property
    def access(self) -> str | None:
        """Get the accessibility of the article.

        :return: Accessibility of the article.
        """
        return self.__access

    @property
    def genres(self) -> list[str]:
        """Get list of genres characterizing the content of the article.

        Genres will be one "PressRelease", "Satire", "Blog", "OpEd", "Opinion", "UserGenerated"
        """
        return self.__genres

    @property
    def keywords(self) -> list[str]:
        """Get list of keywords describing the topic of the article."""
        return self.__keywords

    @property
    def stock_tickers(self) -> list[str]:
        """Get stock tickers that are the main subject of the article.

        Each ticker must be prefixed by the name of its stock exchange, and must match its entry in Google Finance.
        For example, "NASDAQ:AMAT" (but not "NASD:AMAT"), or "BOM:500325" (but not "BOM:RIL").

        Up to 5 tickers can be provided.
        """
        return self.__stock_tickers


class SitemapImage:
    """
    Single image derived from Google Image XML sitemap.

    All properties except ``loc`` are now deprecated in the XML specification, see
    https://developers.google.com/search/blog/2022/05/spring-cleaning-sitemap-extensions

    They will continue to be supported here.
    """

    __slots__ = ["__loc", "__caption", "__geo_location", "__title", "__license"]

    def __init__(
        self,
        loc: str,
        caption: str | None = None,
        geo_location: str | None = None,
        title: str | None = None,
        license_: str | None = None,
    ):
        """Initialise a Google Image.

        :param loc: the URL of the image
        :param caption: the caption of the image, optional
        :param geo_location: the geographic location of the image, for example "Limerick, Ireland", optional
        :param title: the title of the image, optional
        :param license_: a URL to the license of the image, optional
        """
        self.__loc = loc
        self.__caption = caption
        self.__geo_location = geo_location
        self.__title = title
        self.__license = license_

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapImage):
            raise NotImplementedError

        if self.loc != other.loc:
            return False

        if self.caption != other.caption:
            return False

        if self.geo_location != other.geo_location:
            return False

        if self.title != other.title:
            return False

        if self.license != other.license:
            return False

        return True

    def to_dict(self):
        """Convert to a dictionary representation.

        :return: the image data as a dictionary
        """
        return {
            "loc": self.loc,
            "caption": self.caption,
            "geo_location": self.geo_location,
            "title": self.title,
            "license": self.license,
        }

    def __hash__(self):
        return hash(
            (self.loc, self.caption, self.geo_location, self.title, self.license)
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"loc={self.loc}, "
            f"caption={self.caption}, "
            f"geo_location={self.geo_location}, "
            f"title={self.title}, "
            f"license={self.license}"
            ")"
        )

    @property
    def loc(self) -> str:
        """Get the URL of the image."""
        return self.__loc

    @property
    def caption(self) -> str | None:
        """Get the caption of the image."""
        return self.__caption

    @property
    def geo_location(self) -> str | None:
        """Get the geographic location of the image."""
        return self.__geo_location

    @property
    def title(self) -> str | None:
        """Get the title of the image."""
        return self.__title

    @property
    def license(self) -> str | None:
        """Get a URL to the license of the image."""
        return self.__license


SitemapVideoRestriction = tuple[str | None, tuple[str, ...]]
SitemapVideoPrice = tuple[str | None, str | None, str | None, str | None]


class SitemapVideo:
    """Single video derived from a Google Video sitemap or Media RSS feed."""

    __slots__ = [
        "__thumbnail_loc",
        "__title",
        "__description",
        "__content_loc",
        "__player_loc",
        "__duration",
        "__expiration_date",
        "__rating",
        "__view_count",
        "__publication_date",
        "__family_friendly",
        "__restriction",
        "__platform",
        "__requires_subscription",
        "__uploader",
        "__uploader_info",
        "__live",
        "__tags",
        "__prices",
        "__dcterms_valid",
    ]

    def __init__(
        self,
        thumbnail_loc: str | None = None,
        title: str | None = None,
        description: str | None = None,
        content_loc: str | None = None,
        player_loc: str | None = None,
        duration: int | None = None,
        expiration_date: datetime.datetime | None = None,
        rating: Decimal | str | None = None,
        view_count: int | None = None,
        publication_date: datetime.datetime | None = None,
        family_friendly: str | None = None,
        restriction: SitemapVideoRestriction | None = None,
        platform: SitemapVideoRestriction | None = None,
        requires_subscription: str | None = None,
        uploader: str | None = None,
        uploader_info: str | None = None,
        live: str | None = None,
        tags: list[str] | None = None,
        prices: list[SitemapVideoPrice] | None = None,
        dcterms_valid: str | None = None,
    ):
        """Initialise a sitemap video.

        :param thumbnail_loc: URL of a thumbnail image for the video.
        :param title: Video title.
        :param description: Video description.
        :param content_loc: URL of the raw video content file.
        :param player_loc: URL of the video player/embed page.
        :param duration: Duration in seconds.
        :param expiration_date: Date after which the video is no longer available.
        :param rating: Video rating, usually 0.0 to 5.0 for Google Video sitemaps.
        :param view_count: Number of times the video has been viewed.
        :param publication_date: First publication date of the video.
        :param family_friendly: Whether the video is family friendly, usually "yes" or "no".
        :param restriction: Tuple of relationship and restricted values, for example ("allow", ("CA", "MX")).
        :param platform: Tuple of relationship and platforms, for example ("allow", ("web", "tv")).
        :param requires_subscription: Whether a subscription is required, usually "yes" or "no".
        :param uploader: Video uploader name.
        :param uploader_info: URL with more information about the uploader.
        :param live: Whether the video is a livestream, usually "yes" or "no".
        :param tags: Short tags describing the video.
        :param prices: List of price tuples: (price, currency, type, info).
        :param dcterms_valid: Raw dcterms:valid value from Media RSS.
        """
        self.__thumbnail_loc = thumbnail_loc
        self.__title = title
        self.__description = description
        self.__content_loc = content_loc
        self.__player_loc = player_loc
        self.__duration = duration
        self.__expiration_date = expiration_date
        self.__rating = rating
        self.__view_count = view_count
        self.__publication_date = publication_date
        self.__family_friendly = family_friendly
        self.__restriction = restriction
        self.__platform = platform
        self.__requires_subscription = requires_subscription
        self.__uploader = uploader
        self.__uploader_info = uploader_info
        self.__live = live
        self.__tags = tags if tags else []
        self.__prices = prices if prices else []
        self.__dcterms_valid = dcterms_valid

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapVideo):
            raise NotImplementedError

        if self.thumbnail_loc != other.thumbnail_loc:
            return False
        if self.title != other.title:
            return False
        if self.description != other.description:
            return False
        if self.content_loc != other.content_loc:
            return False
        if self.player_loc != other.player_loc:
            return False
        if self.duration != other.duration:
            return False
        if self.expiration_date != other.expiration_date:
            return False
        if self.rating != other.rating:
            return False
        if self.view_count != other.view_count:
            return False
        if self.publication_date != other.publication_date:
            return False
        if self.family_friendly != other.family_friendly:
            return False
        if self.restriction != other.restriction:
            return False
        if self.platform != other.platform:
            return False
        if self.requires_subscription != other.requires_subscription:
            return False
        if self.uploader != other.uploader:
            return False
        if self.uploader_info != other.uploader_info:
            return False
        if self.live != other.live:
            return False
        if self.tags != other.tags:
            return False
        if self.prices != other.prices:
            return False
        if self.dcterms_valid != other.dcterms_valid:
            return False

        return True

    def to_dict(self):
        """Convert to a dictionary representation.

        :return: the video data as a dictionary
        """
        return {
            "thumbnail_loc": self.thumbnail_loc,
            "title": self.title,
            "description": self.description,
            "content_loc": self.content_loc,
            "player_loc": self.player_loc,
            "duration": self.duration,
            "expiration_date": self.expiration_date,
            "rating": self.rating,
            "view_count": self.view_count,
            "publication_date": self.publication_date,
            "family_friendly": self.family_friendly,
            "restriction": {
                "relationship": self.restriction[0],
                "values": list(self.restriction[1]),
            }
            if self.restriction
            else None,
            "platform": {
                "relationship": self.platform[0],
                "values": list(self.platform[1]),
            }
            if self.platform
            else None,
            "requires_subscription": self.requires_subscription,
            "uploader": self.uploader,
            "uploader_info": self.uploader_info,
            "live": self.live,
            "tags": self.tags,
            "prices": [
                {
                    "price": price,
                    "currency": currency,
                    "type": price_type,
                    "info": info,
                }
                for price, currency, price_type, info in self.prices
            ],
            "dcterms_valid": self.dcterms_valid,
        }

    def __hash__(self):
        return hash(
            (
                self.thumbnail_loc,
                self.title,
                self.description,
                self.content_loc,
                self.player_loc,
                self.duration,
                self.expiration_date,
                self.rating,
                self.view_count,
                self.publication_date,
                self.family_friendly,
                self.restriction,
                self.platform,
                self.requires_subscription,
                self.uploader,
                self.uploader_info,
                self.live,
                tuple(self.tags),
                tuple(self.prices),
                self.dcterms_valid,
            )
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"thumbnail_loc={self.thumbnail_loc}, "
            f"title={self.title}, "
            f"description={self.description}, "
            f"content_loc={self.content_loc}, "
            f"player_loc={self.player_loc}, "
            f"duration={self.duration}, "
            f"expiration_date={self.expiration_date}, "
            f"rating={self.rating}, "
            f"view_count={self.view_count}, "
            f"publication_date={self.publication_date}, "
            f"family_friendly={self.family_friendly}, "
            f"restriction={self.restriction}, "
            f"platform={self.platform}, "
            f"requires_subscription={self.requires_subscription}, "
            f"uploader={self.uploader}, "
            f"uploader_info={self.uploader_info}, "
            f"live={self.live}, "
            f"tags={self.tags}, "
            f"prices={self.prices}, "
            f"dcterms_valid={self.dcterms_valid}"
            ")"
        )

    @property
    def thumbnail_loc(self) -> str | None:
        """Get the URL of a thumbnail image for the video."""
        return self.__thumbnail_loc

    @property
    def title(self) -> str | None:
        """Get the video title."""
        return self.__title

    @property
    def description(self) -> str | None:
        """Get the video description."""
        return self.__description

    @property
    def content_loc(self) -> str | None:
        """Get the URL of the raw video content file."""
        return self.__content_loc

    @property
    def player_loc(self) -> str | None:
        """Get the URL of the video player/embed page."""
        return self.__player_loc

    @property
    def duration(self) -> int | None:
        """Get the duration in seconds."""
        return self.__duration

    @property
    def expiration_date(self) -> datetime.datetime | None:
        """Get the date after which the video is no longer available."""
        return self.__expiration_date

    @property
    def rating(self) -> Decimal | str | None:
        """Get the video rating."""
        return self.__rating

    @property
    def view_count(self) -> int | None:
        """Get the view count."""
        return self.__view_count

    @property
    def publication_date(self) -> datetime.datetime | None:
        """Get the first publication date of the video."""
        return self.__publication_date

    @property
    def family_friendly(self) -> str | None:
        """Get whether the video is family friendly."""
        return self.__family_friendly

    @property
    def restriction(self) -> SitemapVideoRestriction | None:
        """Get country or other restrictions for the video."""
        return self.__restriction

    @property
    def platform(self) -> SitemapVideoRestriction | None:
        """Get platform restrictions for the video."""
        return self.__platform

    @property
    def requires_subscription(self) -> str | None:
        """Get whether a subscription is required to view the video."""
        return self.__requires_subscription

    @property
    def uploader(self) -> str | None:
        """Get the video uploader name."""
        return self.__uploader

    @property
    def uploader_info(self) -> str | None:
        """Get the URL with more information about the uploader."""
        return self.__uploader_info

    @property
    def live(self) -> str | None:
        """Get whether the video is a livestream."""
        return self.__live

    @property
    def tags(self) -> list[str]:
        """Get short tags describing the video."""
        return self.__tags

    @property
    def prices(self) -> list[SitemapVideoPrice]:
        """Get Media RSS price entries as (price, currency, type, info) tuples."""
        return self.__prices

    @property
    def dcterms_valid(self) -> str | None:
        """Return dcterms:valid for Yahoo Media RSS."""
        return self.__dcterms_valid


@unique
class SitemapPageChangeFrequency(Enum):
    """Change frequency of a sitemap URL."""

    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NEVER = "never"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Test if enum has specified value."""
        return any(value == item.value for item in cls)


class SitemapPage:
    """Single sitemap-derived page."""

    __slots__ = [
        "__url",
        "__priority",
        "__last_modified",
        "__change_frequency",
        "__news_story",
        "__images",
        "__videos",
        "__alternates",
        "__mobile",
        "__geo",
        "__handheld",
        "__page_map",
        "__code_search",
    ]

    def __init__(
        self,
        url: str,
        priority: Decimal = SITEMAP_PAGE_DEFAULT_PRIORITY,
        last_modified: datetime.datetime | None = None,
        change_frequency: SitemapPageChangeFrequency | None = None,
        news_story: SitemapNewsStory | None = None,
        images: list[SitemapImage] | None = None,
        videos: list[SitemapVideo] | None = None,
        alternates: list[tuple[str, str]] | None = None,
        mobile: "SitemapMobile | None" = None,
        geo: "SitemapGeo | None" = None,
        handheld: str | None = None,
        page_map: "SitemapPageMap | None" = None,
        code_search: "SitemapCodeSearch | None" = None,
    ):
        """
        Initialize new page.

        :param url: Page URL.
        :param priority: Page priority (0.0 to 1.0).
        :param last_modified: Page's last modification date.
        :param change_frequency: How frequently the page is likely to change.
        :param news_story: Google News story.
        :param images: List of Google Image images.
        :param videos: List of Google Video videos.
        :param alternates: List of alternate versions of this page.
        :param mobile: Baidu Mobile info.
        :param geo: Google Geo info.
        :param handheld: URL of the handheld/feature-phone alternate version of this page.
        :param page_map: Google PageMap data.
        :param code_search: Google Code Search metadata.
        """
        self.__url = url
        self.__priority = priority
        self.__last_modified = last_modified
        self.__change_frequency = change_frequency
        self.__news_story = news_story
        self.__images = images
        self.__videos = videos
        self.__alternates = alternates
        self.__mobile = mobile
        self.__geo = geo
        self.__handheld = handheld
        self.__page_map = page_map
        self.__code_search = code_search

    def __eq__(self, other) -> bool:
        """Check equality."""
        if not isinstance(other, SitemapPage):
            raise NotImplementedError

        if self.url != other.url:
            return False

        if self.priority != other.priority:
            return False

        if self.last_modified != other.last_modified:
            return False

        if self.change_frequency != other.change_frequency:
            return False

        if self.news_story != other.news_story:
            return False

        if self.images != other.images:
            return False

        if self.videos != other.videos:
            return False

        if self.alternates != other.alternates:
            return False
        if self.mobile != other.mobile:
            return False
        if self.geo != other.geo:
            return False
        if self.handheld != other.handheld:
            return False
        if self.page_map != other.page_map:
            return False
        if self.code_search != other.code_search:
            return False

        return True

    def __hash__(self):
        return hash(
            (
                # Hash only the URL to be able to find unique pages later on
                self.url,
            )
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"url={self.url}, "
            f"priority={self.priority}, "
            f"last_modified={self.last_modified}, "
            f"change_frequency={self.change_frequency}, "
            f"news_story={self.news_story}, "
            f"images={self.images}, "
            f"videos={self.videos}, "
            f"alternates={self.alternates}, "
            f"mobile={self.mobile}, "
            f"geo={self.geo}, "
            f"handheld={self.handheld}, "
            f"page_map={self.page_map}, "
            f"code_search={self.code_search}"
            ")"
        )

    def to_dict(self):
        """
        Convert this page to a dictionary.
        """

        obj = {
            "url": self.url,
            "priority": self.priority,
            "last_modified": self.last_modified,
            "change_frequency": self.change_frequency.value
            if self.change_frequency
            else None,
            "news_story": self.news_story.to_dict() if self.news_story else None,
            "images": [image.to_dict() for image in self.images]
            if self.images
            else None,
            "videos": [video.to_dict() for video in self.videos]
            if self.videos
            else None,
            "alternates": self.alternates,
        }

        if self.alternates:
            obj["alternates"] = self.alternates

        if self.mobile:
            obj["mobile"] = self.mobile.to_dict()

        if self.geo:
            obj["geo"] = self.geo.to_dict()

        if self.handheld:
            obj["handheld"] = self.handheld

        if self.page_map:
            obj["page_map"] = self.page_map.to_dict()

        if self.code_search:
            obj["code_search"] = self.code_search.to_dict()

        return obj

    @property
    def url(self) -> str:
        """Get the page URL."""
        return self.__url

    @property
    def priority(self) -> Decimal:
        """Get the priority of this URL relative to other URLs on the site."""
        return self.__priority

    @property
    def last_modified(self) -> datetime.datetime | None:
        """Get the date of last modification of the URL."""
        return self.__last_modified

    @property
    def change_frequency(self) -> SitemapPageChangeFrequency | None:
        """Get the change frequency of a sitemap URL."""
        return self.__change_frequency

    @property
    def news_story(self) -> SitemapNewsStory | None:
        """Get the Google News story attached to the URL.

        See :ref:`google-news-ext` reference
        """
        return self.__news_story

    @property
    def images(self) -> list[SitemapImage] | None:
        """Get the images attached to the URL.

        See :ref:`google-image-ext` reference
        """
        return self.__images

    @property
    def videos(self) -> list[SitemapVideo] | None:
        """Get the videos attached to the URL.

        Supports Google Video sitemaps and Media RSS video metadata.
        """
        return self.__videos

    @property
    def alternates(self) -> "list[tuple[str, str]] | None":
        """
        Return a list of alternate versions of this page.
        :return: A list of alternate versions of this page.
        """
        return self.__alternates

    @property
    def mobile(self) -> "SitemapMobile | None":
        """
        Return Baidu Mobile sitemap info.
        :return: Baidu Mobile sitemap info.
        """
        return self.__mobile

    @property
    def geo(self) -> "SitemapGeo | None":
        """
        Return Google Geo sitemap info.
        :return: Google Geo sitemap info.
        """
        return self.__geo

    @property
    def handheld(self) -> str | None:
        """
        Return the URL of the handheld/feature-phone alternate version of this page.
        :return: Handheld alternate URL, or None.
        """
        return self.__handheld

    @property
    def page_map(self) -> "SitemapPageMap | None":
        """
        Return Google PageMap data.
        :return: Google PageMap data, or None.
        """
        return self.__page_map

    @property
    def code_search(self) -> "SitemapCodeSearch | None":
        """
        Return Google Code Search metadata.
        :return: Google Code Search metadata, or None.
        """
        return self.__code_search


class SitemapMobile:
    """Mobile-friendliness of a page, derived from Baidu Mobile XML sitemap."""

    __slots__ = ["__type"]

    def __init__(self, type: str | None = None):
        """
        :param type: The type of mobile page.
        """
        self.__type = type

    def __eq__(self, other) -> bool:
        """Check equality."""
        if not isinstance(other, SitemapMobile):
            return False

        if self.type != other.type:
            return False

        return True

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the mobile info.
        :return: Dictionary representation of the mobile info.
        """
        return {
            "type": self.type,
        }

    def __hash__(self):
        return hash((self.type,))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.type})"

    @property
    def type(self) -> str | None:
        """The type of mobile page."""
        return self.__type


class SitemapGeo:
    """Geo-friendliness of a page, derived from Google Geo XML sitemap."""

    __slots__ = ["__format"]

    def __init__(self, format: str | None = None):
        """
        :param format: The format of the geo file.
        """
        self.__format = format

    def __eq__(self, other) -> bool:
        """Check equality."""
        if not isinstance(other, SitemapGeo):
            return False

        if self.format != other.format:
            return False

        return True

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the geo info.
        :return: Dictionary representation of the geo info.
        """
        return {
            "format": self.format,
        }

    def __hash__(self):
        return hash((self.format,))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(format={self.format})"

    @property
    def format(self) -> str | None:
        """The format of the geo file."""
        return self.__format


class SitemapPageMapAttribute:
    """Single attribute within a PageMap DataObject, from Google PageMap sitemap extension."""

    __slots__ = ["__name", "__value"]

    def __init__(self, name: str, value: str):
        """
        :param name: Attribute name.
        :param value: Attribute value.
        """
        self.__name = name
        self.__value = value

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapPageMapAttribute):
            return False
        return self.name == other.name and self.value == other.value

    def __hash__(self):
        return hash((self.name, self.value))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, value={self.value})"

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value}

    @property
    def name(self) -> str:
        """Attribute name."""
        return self.__name

    @property
    def value(self) -> str:
        """Attribute value."""
        return self.__value


class SitemapPageMapDataObject:
    """DataObject within a PageMap, from Google PageMap sitemap extension."""

    __slots__ = ["__type", "__id", "__attributes"]

    def __init__(
        self,
        type: str | None = None,
        id: str | None = None,
        attributes: list[SitemapPageMapAttribute] | None = None,
    ):
        """
        :param type: DataObject type (e.g. "document").
        :param id: DataObject identifier.
        :param attributes: List of attributes.
        """
        self.__type = type
        self.__id = id
        self.__attributes = attributes if attributes is not None else []

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapPageMapDataObject):
            return False
        return self.type == other.type and self.id == other.id and self.attributes == other.attributes

    def __hash__(self):
        return hash((self.type, self.id, tuple(self.attributes)))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"type={self.type}, id={self.id}, attributes={self.attributes})"
        )

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "id": self.id,
            "attributes": [attr.to_dict() for attr in self.attributes],
        }

    @property
    def type(self) -> str | None:
        """DataObject type."""
        return self.__type

    @property
    def id(self) -> str | None:
        """DataObject identifier."""
        return self.__id

    @property
    def attributes(self) -> list[SitemapPageMapAttribute]:
        """DataObject attributes."""
        return self.__attributes


class SitemapPageMap:
    """PageMap data for a URL, from Google PageMap sitemap extension."""

    __slots__ = ["__data_objects"]

    def __init__(self, data_objects: list[SitemapPageMapDataObject] | None = None):
        """
        :param data_objects: List of DataObjects.
        """
        self.__data_objects = data_objects if data_objects is not None else []

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapPageMap):
            return False
        return self.data_objects == other.data_objects

    def __hash__(self):
        return hash(tuple(self.data_objects))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(data_objects={self.data_objects})"

    def to_dict(self) -> dict:
        return {"data_objects": [obj.to_dict() for obj in self.data_objects]}

    @property
    def data_objects(self) -> list[SitemapPageMapDataObject]:
        """PageMap data objects."""
        return self.__data_objects


class SitemapCodeSearch:
    """Code Search metadata for a URL, from Google Code Search sitemap extension."""

    __slots__ = ["__filetype", "__license", "__filename", "__packageurl", "__packagemap"]

    def __init__(
        self,
        filetype: str | None = None,
        license: str | None = None,
        filename: str | None = None,
        packageurl: str | None = None,
        packagemap: str | None = None,
    ):
        """
        :param filetype: Source code language (e.g. "C", "Python") or "archive".
        :param license: Software license short name (e.g. "GPL", "BSD").
        :param filename: Actual file name if the URL does not reveal it.
        :param packageurl: URL of the top-level package directory.
        :param packagemap: Name of the packagemap file inside the archive.
        """
        self.__filetype = filetype
        self.__license = license
        self.__filename = filename
        self.__packageurl = packageurl
        self.__packagemap = packagemap

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapCodeSearch):
            return False
        return (
            self.filetype == other.filetype
            and self.license == other.license
            and self.filename == other.filename
            and self.packageurl == other.packageurl
            and self.packagemap == other.packagemap
        )

    def __hash__(self):
        return hash((self.filetype, self.license, self.filename, self.packageurl, self.packagemap))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"filetype={self.filetype}, "
            f"license={self.license}, "
            f"filename={self.filename}, "
            f"packageurl={self.packageurl}, "
            f"packagemap={self.packagemap})"
        )

    def to_dict(self) -> dict:
        return {
            "filetype": self.filetype,
            "license": self.license,
            "filename": self.filename,
            "packageurl": self.packageurl,
            "packagemap": self.packagemap,
        }

    @property
    def filetype(self) -> str | None:
        """Source code language or \"archive\"."""
        return self.__filetype

    @property
    def license(self) -> str | None:
        """Software license short name."""
        return self.__license

    @property
    def filename(self) -> str | None:
        """Actual file name."""
        return self.__filename

    @property
    def packageurl(self) -> str | None:
        """URL of the top-level package directory."""
        return self.__packageurl

    @property
    def packagemap(self) -> str | None:
        """Name of the packagemap file inside the archive."""
        return self.__packagemap


class SitemapSemanticWebLinkedDataPrefix:
    """Linked Data prefix for Semantic Web crawling extension."""

    __slots__ = ["__namespace", "__prefix_value", "__slice_method"]

    def __init__(self, namespace: str, prefix_value: str, slice_method: str | None = None):
        """
        :param namespace: Namespace URI for the linked data prefix.
        :param prefix_value: Short prefix identifier for the namespace.
        :param slice_method: Slicing method: "URI", "Regex", or "None".
        """
        self.__namespace = namespace
        self.__prefix_value = prefix_value
        self.__slice_method = slice_method

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapSemanticWebLinkedDataPrefix):
            return False
        return (
            self.namespace == other.namespace
            and self.prefix_value == other.prefix_value
            and self.slice_method == other.slice_method
        )

    def __hash__(self):
        return hash((self.namespace, self.prefix_value, self.slice_method))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(namespace={self.namespace}, prefix_value={self.prefix_value}, slice_method={self.slice_method})"

    def to_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "prefix_value": self.prefix_value,
            "slice_method": self.slice_method,
        }

    @property
    def namespace(self) -> str:
        """Namespace URI for the linked data prefix."""
        return self.__namespace

    @property
    def prefix_value(self) -> str:
        """Short prefix identifier for the namespace."""
        return self.__prefix_value

    @property
    def slice_method(self) -> str | None:
        """Slicing method used for descriptions."""
        return self.__slice_method


class SitemapSemanticWebSparqlEndpoint:
    """SPARQL endpoint for Semantic Web crawling extension."""

    __slots__ = ["__location", "__slice_method", "__graph_name"]

    def __init__(self, location: str, graph_name: str | None = None, slice_method: str | None = None):
        """
        :param location: SPARQL endpoint URL.
        :param graph_name: Named graph URI, or "*" for all graphs.
        :param slice_method: Slicing method: "URI", "Regex", or "None".
        """
        self.__location = location
        self.__slice_method = slice_method
        self.__graph_name = graph_name

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapSemanticWebSparqlEndpoint):
            return False
        return (
            self.location == other.location
            and self.slice_method == other.slice_method
            and self.graph_name == other.graph_name
        )

    def __hash__(self):
        return hash((self.location, self.slice_method, self.graph_name))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"location={self.location}, graph_name={self.graph_name}, slice_method={self.slice_method})"
        )

    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "graph_name": self.graph_name,
            "slice_method": self.slice_method,
        }

    @property
    def location(self) -> str:
        """SPARQL endpoint URL."""
        return self.__location

    @property
    def slice_method(self) -> str | None:
        """Slicing method used for DESCRIBE queries."""
        return self.__slice_method

    @property
    def graph_name(self) -> str | None:
        """Named graph URI in the endpoint."""
        return self.__graph_name


class SitemapSemanticWebDataset:
    """RDF dataset from Semantic Web crawling sitemap extension."""

    __slots__ = [
        "__label",
        "__dataset_uri",
        "__linked_data_prefixes",
        "__sparql_endpoint",
        "__data_dump_locations",
        "__sample_uris",
        "__last_modified",
        "__change_frequency",
    ]

    def __init__(
        self,
        label: str | None = None,
        dataset_uri: str | None = None,
        linked_data_prefixes: list[SitemapSemanticWebLinkedDataPrefix] | None = None,
        sparql_endpoint: SitemapSemanticWebSparqlEndpoint | None = None,
        data_dump_locations: list[str] | None = None,
        sample_uris: list[str] | None = None,
        last_modified: datetime.datetime | None = None,
        change_frequency: str | None = None,
    ):
        """
        :param label: Human-readable dataset name.
        :param dataset_uri: URI identifying the dataset.
        :param linked_data_prefixes: List of Linked Data URI prefixes.
        :param sparql_endpoint: SPARQL endpoint for the dataset.
        :param data_dump_locations: List of RDF dump file URLs.
        :param sample_uris: List of sample URIs in the dataset.
        :param last_modified: Last modification date of the dataset.
        :param change_frequency: Expected update frequency (always, hourly, daily, weekly, monthly, yearly, never).
        """
        self.__label = label
        self.__dataset_uri = dataset_uri
        self.__linked_data_prefixes = linked_data_prefixes if linked_data_prefixes is not None else []
        self.__sparql_endpoint = sparql_endpoint
        self.__data_dump_locations = data_dump_locations if data_dump_locations is not None else []
        self.__sample_uris = sample_uris if sample_uris is not None else []
        self.__last_modified = last_modified
        self.__change_frequency = change_frequency

    def __eq__(self, other) -> bool:
        if not isinstance(other, SitemapSemanticWebDataset):
            return False
        return (
            self.label == other.label
            and self.dataset_uri == other.dataset_uri
            and self.linked_data_prefixes == other.linked_data_prefixes
            and self.sparql_endpoint == other.sparql_endpoint
            and self.data_dump_locations == other.data_dump_locations
            and self.sample_uris == other.sample_uris
            and self.last_modified == other.last_modified
            and self.change_frequency == other.change_frequency
        )

    def __hash__(self):
        return hash(
            (
                self.label,
                self.dataset_uri,
                tuple(self.linked_data_prefixes),
                self.sparql_endpoint,
                tuple(self.data_dump_locations),
                tuple(self.sample_uris),
                self.last_modified,
                self.change_frequency,
            )
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"label={self.label}, dataset_uri={self.dataset_uri}, "
            f"linked_data_prefixes={self.linked_data_prefixes}, "
            f"sparql_endpoint={self.sparql_endpoint}, "
            f"data_dump_locations={self.data_dump_locations}, "
            f"sample_uris={self.sample_uris}, "
            f"last_modified={self.last_modified}, "
            f"change_frequency={self.change_frequency})"
        )

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "dataset_uri": self.dataset_uri,
            "linked_data_prefixes": [p.to_dict() for p in self.linked_data_prefixes],
            "sparql_endpoint": self.sparql_endpoint.to_dict() if self.sparql_endpoint else None,
            "data_dump_locations": self.data_dump_locations,
            "sample_uris": self.sample_uris,
            "last_modified": self.last_modified,
            "change_frequency": self.change_frequency,
        }

    @property
    def label(self) -> str | None:
        """Human-readable dataset name."""
        return self.__label

    @property
    def dataset_uri(self) -> str | None:
        """URI identifying the dataset."""
        return self.__dataset_uri

    @property
    def linked_data_prefixes(self) -> list[SitemapSemanticWebLinkedDataPrefix]:
        """List of Linked Data URI prefixes."""
        return self.__linked_data_prefixes

    @property
    def sparql_endpoint(self) -> SitemapSemanticWebSparqlEndpoint | None:
        """SPARQL endpoint for the dataset."""
        return self.__sparql_endpoint

    @property
    def data_dump_locations(self) -> list[str]:
        """List of RDF dump file URLs."""
        return self.__data_dump_locations

    @property
    def sample_uris(self) -> list[str]:
        """List of sample URIs in the dataset."""
        return self.__sample_uris

    @property
    def last_modified(self) -> datetime.datetime | None:
        """Last modification date of the dataset."""
        return self.__last_modified

    @property
    def change_frequency(self) -> str | None:
        """Expected update frequency."""
        return self.__change_frequency
