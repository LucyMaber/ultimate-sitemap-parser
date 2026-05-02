import textwrap
from decimal import Decimal
from unittest import mock

from tests.tree.base import TreeTestBase
from usp.objects.page import SitemapImage, SitemapPage, SitemapVideo
from usp.objects.sitemap import (
    IndexRobotsTxtSitemap,
    IndexWebsiteSitemap,
    PagesXMLSitemap,
)
from usp.tree import sitemap_tree_for_homepage


class TestXMLExts(TreeTestBase):
    def test_video_pages_callback(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_video.xml
                Sitemap: {self.TEST_BASE_URL}/sitemap_pages.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_video.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                    xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
                  <url>
                    <loc>{self.TEST_BASE_URL}/video-story.html</loc>
                    <video:video>
                      <video:thumbnail_loc>{self.TEST_BASE_URL}/thumb.jpg</video:thumbnail_loc>
                      <video:title>Example Video</video:title>
                      <video:description>Example description</video:description>
                    </video:video>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_pages.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url>
                    <loc>{self.TEST_BASE_URL}/regular-page.html</loc>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        def recurse_list_callback(
            urls: list[str], recursion_level: int, parent_urls: set[str]
        ) -> list[str]:
            assert recursion_level >= 0
            _ = parent_urls
            return [url for url in urls if "video" in url]

        get_media_file = mock.Mock()

        tree = sitemap_tree_for_homepage(
            self.TEST_BASE_URL, recurse_list_callback=recurse_list_callback
        )

        for page in tree.all_pages():
            if page.videos:
                get_media_file(page.url)

        get_media_file.assert_called_once_with(f"{self.TEST_BASE_URL}/video-story.html")

    def test_xml_image(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_images.xml

            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_images.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                    xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
                  <url>
                    <loc>{self.TEST_BASE_URL}/sample1.html</loc>
                    <image:image>
                      <image:loc>{self.TEST_BASE_URL}/image.jpg</image:loc>
                      <image:caption>Example Caption</image:caption>
                      <image:geo_location>Sheffield, UK</image:geo_location>
                      <image:title>Example Title</image:title>
                      <image:license>https://creativecommons.org/publicdomain/zero/1.0/</image:license>
                    </image:image>
                    <image:image>
                      <image:loc>{self.TEST_BASE_URL}/photo.jpg</image:loc>
                    </image:image>
                  </url>
                  <url>
                    <loc>{self.TEST_BASE_URL}/sample2.html</loc>
                    <image:image>
                      <image:loc>{self.TEST_BASE_URL}/picture.jpg</image:loc>
                    </image:image>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        expected_sitemap_tree = IndexWebsiteSitemap(
            url=f"{self.TEST_BASE_URL}/",
            sub_sitemaps=[
                IndexRobotsTxtSitemap(
                    url=f"{self.TEST_BASE_URL}/robots.txt",
                    sub_sitemaps=[
                        PagesXMLSitemap(
                            url=f"{self.TEST_BASE_URL}/sitemap_images.xml",
                            pages=[
                                SitemapPage(
                                    url=f"{self.TEST_BASE_URL}/sample1.html",
                                    images=[
                                        SitemapImage(
                                            loc=f"{self.TEST_BASE_URL}/image.jpg",
                                            caption="Example Caption",
                                            geo_location="Sheffield, UK",
                                            title="Example Title",
                                            license_="https://creativecommons.org/publicdomain/zero/1.0/",
                                        ),
                                        SitemapImage(
                                            loc=f"{self.TEST_BASE_URL}/photo.jpg"
                                        ),
                                    ],
                                ),
                                SitemapPage(
                                    url=f"{self.TEST_BASE_URL}/sample2.html",
                                    images=[
                                        SitemapImage(
                                            loc=f"{self.TEST_BASE_URL}/picture.jpg"
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ],
                )
            ],
        )

        print(tree.to_dict())
        print(tree)

        assert tree == expected_sitemap_tree

    def test_xml_google_video(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_video.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_video.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                    xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
                  <url>
                    <loc>{self.TEST_BASE_URL}/video-story.html</loc>
                    <video:video>
                      <video:thumbnail_loc>{self.TEST_BASE_URL}/thumb.jpg</video:thumbnail_loc>
                      <video:title>Example Video</video:title>
                      <video:description>Example description</video:description>
                      <video:content_loc>{self.TEST_BASE_URL}/video.mp4</video:content_loc>
                      <video:player_loc>{self.TEST_BASE_URL}/player.html</video:player_loc>
                      <video:duration>120</video:duration>
                      <video:expiration_date>{self.TEST_DATE_STR_ISO8601}</video:expiration_date>
                      <video:rating>4.2</video:rating>
                      <video:view_count>321</video:view_count>
                      <video:publication_date>{self.TEST_DATE_STR_ISO8601}</video:publication_date>
                      <video:family_friendly>yes</video:family_friendly>
                      <video:restriction relationship="allow">US GB</video:restriction>
                      <video:platform relationship="deny">tv</video:platform>
                      <video:requires_subscription>yes</video:requires_subscription>
                      <video:uploader info="{self.TEST_BASE_URL}/authors/alice">Alice</video:uploader>
                      <video:live>no</video:live>
                      <video:tag>tag-one</video:tag>
                      <video:tag>tag-two</video:tag>
                    </video:video>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == f"{self.TEST_BASE_URL}/video-story.html"
        assert pages[0].videos == [
            SitemapVideo(
                thumbnail_loc=f"{self.TEST_BASE_URL}/thumb.jpg",
                title="Example Video",
                description="Example description",
                content_loc=f"{self.TEST_BASE_URL}/video.mp4",
                player_loc=f"{self.TEST_BASE_URL}/player.html",
                duration=120,
                expiration_date=self.TEST_DATE_DATETIME,
                rating=Decimal("4.2"),
                view_count=321,
                publication_date=self.TEST_DATE_DATETIME,
                family_friendly="yes",
                restriction=("allow", ("US", "GB")),
                platform=("deny", ("tv",)),
                requires_subscription="yes",
                uploader="Alice",
                uploader_info=f"{self.TEST_BASE_URL}/authors/alice",
                live="no",
                tags=["tag-one", "tag-two"],
            )
        ]

    def test_rss_media(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_media_rss.xml
            """
            ).strip(),
        )

        media_end_date = "2009-12-18T12:04:56+02:00"

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_media_rss.xml",
            headers={"Content-Type": "application/rss+xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0"
                    xmlns:media="http://search.yahoo.com/mrss/"
                    xmlns:dcterms="http://purl.org/dc/terms/">
                  <channel>
                    <title>Media RSS Feed</title>
                    <item>
                      <title>Media Story</title>
                      <description>Media story description</description>
                      <link>{self.TEST_BASE_URL}/media-story.html</link>
                      <pubDate>{self.TEST_DATE_STR_RFC2822}</pubDate>
                      <media:content url="{self.TEST_BASE_URL}/media.mp4" duration="300" />
                      <media:thumbnail url="{self.TEST_BASE_URL}/media-thumb.jpg" />
                      <media:player url="{self.TEST_BASE_URL}/media-player.html" />
                      <media:title>Media Title</media:title>
                      <media:description>Media Description</media:description>
                      <media:rating>3.5</media:rating>
                      <media:restriction relationship="allow">US CA</media:restriction>
                      <media:keywords>tag-a, tag-b</media:keywords>
                      <media:category>tag-c</media:category>
                      <media:price currency="USD" type="rent" info="HD">9.99</media:price>
                      <media:credit>Alice</media:credit>
                      <dcterms:valid>start={self.TEST_DATE_STR_ISO8601}; end={media_end_date}; scheme=W3C-DTF</dcterms:valid>
                    </item>
                  </channel>
                </rss>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == f"{self.TEST_BASE_URL}/media-story.html"
        assert pages[0].videos == [
            SitemapVideo(
                thumbnail_loc=f"{self.TEST_BASE_URL}/media-thumb.jpg",
                title="Media Title",
                description="Media Description",
                content_loc=f"{self.TEST_BASE_URL}/media.mp4",
                player_loc=f"{self.TEST_BASE_URL}/media-player.html",
                duration=300,
                expiration_date=self.TEST_DATE_DATETIME.replace(day=18),
                rating=Decimal("3.5"),
                publication_date=self.TEST_DATE_DATETIME,
                restriction=("allow", ("US", "CA")),
                uploader="Alice",
                tags=["tag-a", "tag-b", "tag-c"],
                prices=[("9.99", "USD", "rent", "HD")],
                dcterms_valid=f"start={self.TEST_DATE_STR_ISO8601}; end={media_end_date}; scheme=W3C-DTF",
            )
        ]


class TestXMLHrefLang(TreeTestBase):
    def test_hreflang(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
                    <url>
                        <loc>{self.TEST_BASE_URL}/en/page</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link rel="alternate" hreflang="fr-FR" href="{self.TEST_BASE_URL}/fr/page"/>
                    </url>
                    <url>
                        <loc>{self.TEST_BASE_URL}/fr/page</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link rel="alternate" hreflang="en-GB" href="{self.TEST_BASE_URL}/en/page"/>
                    </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert pages[0].alternates == [
            ("fr-FR", f"{self.TEST_BASE_URL}/fr/page"),
        ]
        assert pages[1].alternates == [
            ("en-GB", f"{self.TEST_BASE_URL}/en/page"),
        ]

    def test_missing_attrs(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
                    <url>
                        <loc>{self.TEST_BASE_URL}/en/page</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link rel="alternate" href="{self.TEST_BASE_URL}/fr/page"/>
                    </url>
                    <url>
                        <loc>{self.TEST_BASE_URL}/en/page2</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link hreflang="fr-FR" href="{self.TEST_BASE_URL}/fr/page2"/>
                    </url>
                    <url>
                        <loc>{self.TEST_BASE_URL}/fr/page</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link rel="alternate" hreflang="en-GB"/>
                    </url>
                    <url>
                        <loc>{self.TEST_BASE_URL}/fr/page2</loc>
                        <lastmod>{self.TEST_DATE_STR_ISO8601}</lastmod>
                        <changefreq>monthly</changefreq>
                        <priority>0.8</priority>
                        <xhtml:link hreflang="en-GB" href="{self.TEST_BASE_URL}/en/page2"/>
                    </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert pages[0].alternates is None
        assert pages[1].alternates is None
        assert pages[2].alternates is None
        assert pages[3].alternates is None
