import textwrap
from decimal import Decimal
from unittest import mock

from tests.tree.base import TreeTestBase
from usp.objects.page import (
    SitemapImage,
    SitemapPage,
    SitemapVideo,
    SitemapMobile,
    SitemapGeo,
    SitemapPageMap,
    SitemapPageMapAttribute,
    SitemapPageMapDataObject,
    SitemapCodeSearch,
)
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

    def test_xml_mobile(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_mobile.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_mobile.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset
                  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                  xmlns:mobile="http://www.baidu.com/schemas/sitemap-mobile/1/">
                  <url>
                    <loc>http://m.abc.com/index.html</loc>
                    <mobile:mobile type="mobile"/>
                    <lastmod>2009-12-14</lastmod>
                    <changefreq>daily</changefreq>
                    <priority>0.8</priority>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == "http://m.abc.com/index.html"
        assert pages[0].mobile == SitemapMobile(type="mobile")

    def test_xml_geo(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_geo.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_geo.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                        xmlns:geo="http://www.google.com/geo/schemas/sitemap/1.0">
                  <url>
                    <loc>https://www.example.com/locations.kml</loc>
                    <geo:geo>
                      <geo:format>kml</geo:format>
                    </geo:geo>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == "https://www.example.com/locations.kml"
        assert pages[0].geo == SitemapGeo(format="kml")

    def test_xml_pagemap(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_pagemap.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_pagemap.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url>
                    <loc>{self.TEST_BASE_URL}/foo</loc>
                    <PageMap xmlns="http://www.google.com/schemas/sitemap-pagemap/1.0">
                      <DataObject type="document" id="hibachi">
                        <Attribute name="name">Dragon</Attribute>
                        <Attribute name="review">3.5</Attribute>
                      </DataObject>
                    </PageMap>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == f"{self.TEST_BASE_URL}/foo"
        assert pages[0].page_map == SitemapPageMap(
            data_objects=[
                SitemapPageMapDataObject(
                    type="document",
                    id="hibachi",
                    attributes=[
                        SitemapPageMapAttribute(name="name", value="Dragon"),
                        SitemapPageMapAttribute(name="review", value="3.5"),
                    ],
                )
            ]
        )

    def test_xml_codesearch(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_codesearch.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_codesearch.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                        xmlns:codesearch="http://www.google.com/codesearch/schemas/sitemap/1.0">
                  <url>
                    <loc>http://mysite.org/download/myfile.c</loc>
                    <codesearch:codesearch>
                      <codesearch:filetype>C</codesearch:filetype>
                      <codesearch:license>LGPL</codesearch:license>
                    </codesearch:codesearch>
                  </url>
                  <url>
                    <loc>http://mysite.org/download/myproject.tgz</loc>
                    <codesearch:codesearch>
                      <codesearch:filetype>archive</codesearch:filetype>
                      <codesearch:license>Apache</codesearch:license>
                      <codesearch:packagemap>packagemap.xml</codesearch:packagemap>
                    </codesearch:codesearch>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 2
        assert pages[0].url == "http://mysite.org/download/myfile.c"
        assert pages[0].code_search == SitemapCodeSearch(filetype="C", license="LGPL")
        assert pages[1].url == "http://mysite.org/download/myproject.tgz"
        assert pages[1].code_search == SitemapCodeSearch(
            filetype="archive", license="Apache", packagemap="packagemap.xml"
        )

    def test_xml_handheld(self, requests_mock):
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)

        requests_mock.get(
            self.TEST_BASE_URL + "/robots.txt",
            headers={"Content-Type": "text/plain"},
            text=textwrap.dedent(
                f"""
                User-agent: *
                Disallow: /whatever

                Sitemap: {self.TEST_BASE_URL}/sitemap_handheld.xml
            """
            ).strip(),
        )

        requests_mock.get(
            self.TEST_BASE_URL + "/sitemap_handheld.xml",
            headers={"Content-Type": "text/xml"},
            text=textwrap.dedent(
                f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                        xmlns:xhtml="http://www.w3.org/1999/xhtml">
                  <url>
                    <loc>{self.TEST_BASE_URL}/page</loc>
                    <xhtml:link rel="alternate" media="handheld" href="{self.TEST_BASE_URL}/page"/>
                  </url>
                </urlset>
                """
            ).strip(),
        )

        tree = sitemap_tree_for_homepage(self.TEST_BASE_URL)

        pages = list(tree.all_pages())
        assert len(pages) == 1
        assert pages[0].url == f"{self.TEST_BASE_URL}/page"
        assert pages[0].handheld == f"{self.TEST_BASE_URL}/page"

    def test_xml_semantic_web(self, requests_mock):
        """Test Semantic Web (RDF) sitemap parsing."""
        from usp.objects.sitemap import SemanticWebSitemap
        from usp.fetch_parse import XMLSitemapParser
        from usp.web_client.requests_client import RequestsWebClient
        
        # We'll test the parser directly using XMLSitemapParser
        # Set up minimal mocking
        requests_mock.add_matcher(TreeTestBase.fallback_to_404_not_found_matcher)
        
        xml_content = textwrap.dedent("""
            <?xml version="1.0" encoding="UTF-8"?>
            <sc:dataset
                xmlns:sc="http://sw.deri.org/2007/07/sitemapextension/scschema.xsd"
                xmlns:void="http://rdfs.org/ns/void#">
              <sc:datasetLabel>Example RDF Dataset</sc:datasetLabel>
              <sc:datasetURI>http://example.org/dataset</sc:datasetURI>
              <sc:linkedDataPrefix sliceMethod="URI">
                <sc:namespace>http://example.org/vocab/</sc:namespace>
                <sc:prefix>ex</sc:prefix>
              </sc:linkedDataPrefix>
              <sc:linkedDataPrefix sliceMethod="Regex">
                <sc:namespace>http://example.org/resource/</sc:namespace>
                <sc:prefix>exres</sc:prefix>
              </sc:linkedDataPrefix>
              <sc:sparqlEndpointLocation sliceMethod="None">
                <sc:endpointURI>http://example.org/sparql</sc:endpointURI>
                <sc:sparqlGraphName>http://example.org/graph</sc:sparqlGraphName>
              </sc:sparqlEndpointLocation>
              <sc:dataDumpLocation>http://example.org/data/dataset.nt</sc:dataDumpLocation>
              <sc:dataDumpLocation>http://example.org/data/dataset.ttl</sc:dataDumpLocation>
              <sc:sampleURI>http://example.org/resource/sample1</sc:sampleURI>
              <sc:sampleURI>http://example.org/resource/sample2</sc:sampleURI>
              <lastmod>2024-01-15T12:30:00Z</lastmod>
              <changefreq>monthly</changefreq>
            </sc:dataset>
        """).strip()
        
        # Create parser and parse
        sitemap_parser = XMLSitemapParser(
            url="http://example.org/dataset.xml",
            content=xml_content,
            recursion_level=0,
            web_client=RequestsWebClient(),
            parent_urls=set(),
            recurse_callback=None,
            recurse_list_callback=None,
        )
        
        sitemap = sitemap_parser.sitemap()
        
        # Verify it's a SemanticWebSitemap
        assert isinstance(sitemap, SemanticWebSitemap)
        
        # Verify datasets
        assert len(sitemap.datasets) == 1
        dataset = sitemap.datasets[0]
        
        # Verify dataset metadata
        assert dataset.label == "Example RDF Dataset"
        assert dataset.dataset_uri == "http://example.org/dataset"
        assert dataset.last_modified == "2024-01-15T12:30:00Z"
        assert dataset.change_frequency == "monthly"
        
        # Verify linked data prefixes
        assert len(dataset.linked_data_prefixes) == 2
        assert dataset.linked_data_prefixes[0].namespace == "http://example.org/vocab/"
        assert dataset.linked_data_prefixes[0].prefix_value == "ex"
        assert dataset.linked_data_prefixes[0].slice_method == "URI"
        assert dataset.linked_data_prefixes[1].namespace == "http://example.org/resource/"
        assert dataset.linked_data_prefixes[1].prefix_value == "exres"
        assert dataset.linked_data_prefixes[1].slice_method == "Regex"
        
        # Verify SPARQL endpoint
        assert dataset.sparql_endpoint is not None
        assert dataset.sparql_endpoint.location == "http://example.org/sparql"
        assert dataset.sparql_endpoint.graph_name == "http://example.org/graph"
        assert dataset.sparql_endpoint.slice_method == "None"
        
        # Verify data dumps
        assert len(dataset.data_dump_locations) == 2
        assert "http://example.org/data/dataset.nt" in dataset.data_dump_locations
        assert "http://example.org/data/dataset.ttl" in dataset.data_dump_locations
        
        # Verify samples
        assert len(dataset.sample_uris) == 2
        assert "http://example.org/resource/sample1" in dataset.sample_uris
        assert "http://example.org/resource/sample2" in dataset.sample_uris
