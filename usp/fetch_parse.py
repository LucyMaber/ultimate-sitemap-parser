"""Sitemap fetchers and parsers.

.. seealso::

    :doc:`Reference of classes used for each format </reference/formats>`

    :doc:`Overview of parse process </guides/fetch-parse>`
"""

import abc
import datetime
import logging
import re
import xml.parsers.expat
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from .exceptions import SitemapException, SitemapXMLParsingException
from .helpers import (
    RecurseCallbackType,
    RecurseListCallbackType,
    get_url_retry_on_client_errors,
    html_unescape_strip,
    is_http_url,
    parse_iso8601_date,
    parse_rfc2822_date,
    ungzipped_response_content,
)
from .objects.page import (
    SITEMAP_PAGE_DEFAULT_PRIORITY,
    SitemapImage,
    SitemapNewsStory,
    SitemapPage,
    SitemapPageChangeFrequency,
    SitemapVideo,
    SitemapVideoPrice,
    SitemapVideoRestriction,
    SitemapMobile,
    SitemapGeo,
    SitemapPageMap,
    SitemapPageMapAttribute,
    SitemapPageMapDataObject,
    SitemapCodeSearch,
    SitemapSemanticWebDataset,
    SitemapSemanticWebLinkedDataPrefix,
    SitemapSemanticWebSparqlEndpoint,
)
from .objects.sitemap import (
    AbstractSitemap,
    IndexRobotsTxtSitemap,
    IndexXMLSitemap,
    InvalidSitemap,
    PagesAtomSitemap,
    PagesRSSSitemap,
    PagesTextSitemap,
    PagesXMLSitemap,
    SemanticWebSitemap,
)
from .web_client.abstract_client import (
    AbstractWebClient,
    AbstractWebClientResponse,
    AbstractWebClientSuccessResponse,
    LocalWebClient,
    LocalWebClientSuccessResponse,
    NoWebClientException,
    WebClientErrorResponse,
)
from .web_client.requests_client import RequestsWebClient

log = logging.getLogger(__name__)


class SitemapFetcher:
    """
    Fetches and parses the sitemap at a given URL, and any declared sub-sitemaps.
    """

    __MAX_SITEMAP_SIZE = 100 * 1024 * 1024
    """Max. uncompressed sitemap size.

    Spec says it might be up to 50 MB but let's go for the full 100 MB here."""

    __MAX_RECURSION_LEVEL = 11
    """Max. depth level in iterating over sub-sitemaps.
    
    Recursive sitemaps (i.e. child sitemaps pointing to their parent) are stopped immediately.
    """

    __slots__ = [
        "_url",
        "_recursion_level",
        "_web_client",
        "_parent_urls",
        "_quiet_404",
        "_recurse_callback",
        "_recurse_list_callback",
    ]

    def __init__(
        self,
        url: str,
        recursion_level: int,
        web_client: AbstractWebClient | None = None,
        parent_urls: set[str] | None = None,
        quiet_404: bool = False,
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        """

        :param url: URL of the sitemap to fetch and parse.
        :param recursion_level: current recursion level of parser
        :param web_client: Web client to use. If ``None``, a :class:`~.RequestsWebClient` will be used.
        :param parent_urls: Set of parent URLs that led to this sitemap.
        :param quiet_404: Whether 404 errors are expected and should be logged at a reduced level, useful for speculative fetching of known URLs.
        :param recurse_callback: Optional callback to filter out a sub-sitemap. See :data:`~.RecurseCallbackType`.
        :param recurse_list_callback: Optional callback to filter the list of sub-sitemaps. See :data:`~.RecurseListCallbackType`.

        :raises SitemapException: If the maximum recursion depth is exceeded.
        :raises SitemapException: If the URL is in the parent URLs set.
        :raises SitemapException: If the URL is not an HTTP(S) URL
        """
        if recursion_level > self.__MAX_RECURSION_LEVEL:
            raise SitemapException(
                f"Recursion level exceeded {self.__MAX_RECURSION_LEVEL} for URL {url}."
            )

        log.debug(f"Parent URLs is {parent_urls}")

        if not is_http_url(url):
            raise SitemapException(f"URL {url} is not a HTTP(s) URL.")

        parent_urls = parent_urls or set()

        if url in parent_urls:
            # Likely a sitemap index points to itself/a higher level index
            raise SitemapException(
                f"Recursion detected in URL {url} with parent URLs {parent_urls}."
            )

        if not web_client:
            web_client = RequestsWebClient()

        web_client.set_max_response_data_length(self.__MAX_SITEMAP_SIZE)

        self._url = url
        self._web_client = web_client
        self._recursion_level = recursion_level
        self._parent_urls = parent_urls or set()
        self._quiet_404 = quiet_404

        self._recurse_callback = recurse_callback
        self._recurse_list_callback = recurse_list_callback

    def _fetch(self) -> AbstractWebClientResponse:
        log.info(f"Fetching level {self._recursion_level} sitemap from {self._url}...")
        response = get_url_retry_on_client_errors(
            url=self._url, web_client=self._web_client, quiet_404=self._quiet_404
        )
        return response

    def sitemap(self) -> AbstractSitemap:
        """
        Fetch and parse the sitemap.

        :return: the parsed sitemap. Will be a child of :class:`~.AbstractSitemap`.
            If an HTTP error is encountered, or the sitemap cannot be parsed, will be :class:`~.InvalidSitemap`.
        """
        response = self._fetch()

        if isinstance(response, WebClientErrorResponse):
            return InvalidSitemap(
                url=self._url,
                reason=f"Unable to fetch sitemap from {self._url}: {response.message()}",
            )
        assert isinstance(response, AbstractWebClientSuccessResponse)

        response_url = response.url()
        log.debug(f"Response URL is {response_url}")
        if response_url in self._parent_urls:
            # Likely a sitemap has redirected to a parent URL
            return InvalidSitemap(
                url=self._url,
                reason=f"Recursion detected when {self._url} redirected to {response_url} with parent URLs {self._parent_urls}.",
            )

        self._url = response_url

        response_content = ungzipped_response_content(url=self._url, response=response)

        # MIME types returned in Content-Type are unpredictable, so peek into the content instead
        if response_content[:20].strip().startswith("<"):
            # XML sitemap (the specific kind is to be determined later)
            parser: AbstractSitemapParser = XMLSitemapParser(
                url=self._url,
                content=response_content,
                recursion_level=self._recursion_level,
                web_client=self._web_client,
                parent_urls=self._parent_urls,
                recurse_callback=self._recurse_callback,
                recurse_list_callback=self._recurse_list_callback,
            )

        else:
            # Assume that it's some sort of a text file (robots.txt or plain text sitemap)
            if self._url.endswith("/robots.txt"):
                parser = IndexRobotsTxtSitemapParser(
                    url=self._url,
                    content=response_content,
                    recursion_level=self._recursion_level,
                    web_client=self._web_client,
                    parent_urls=self._parent_urls,
                    recurse_callback=self._recurse_callback,
                    recurse_list_callback=self._recurse_list_callback,
                )
            else:
                parser = PlainTextSitemapParser(
                    url=self._url,
                    content=response_content,
                    recursion_level=self._recursion_level,
                    web_client=self._web_client,
                    parent_urls=self._parent_urls,
                )

        log.info(f"Parsing sitemap from URL {self._url}...")
        sitemap = parser.sitemap()

        return sitemap


class SitemapStrParser(SitemapFetcher):
    """Custom fetcher to parse a string instead of download from a URL.

    This is a little bit hacky, but it allows us to support local content parsing without
    having to change too much.
    """

    __slots__ = ["_static_content"]

    def __init__(self, static_content: str):
        """Init a new string parser

        :param static_content: String containing sitemap text to parse
        """
        super().__init__(
            url="http://usp-local-dummy.local/",
            recursion_level=0,
            web_client=LocalWebClient(),
        )
        self._static_content = static_content

    def _fetch(self) -> AbstractWebClientResponse:
        return LocalWebClientSuccessResponse(url=self._url, data=self._static_content)


class AbstractSitemapParser(metaclass=abc.ABCMeta):
    """Abstract robots.txt / XML / plain text sitemap parser."""

    __slots__ = [
        "_url",
        "_content",
        "_web_client",
        "_recursion_level",
        "_parent_urls",
        "_recurse_callback",
        "_recurse_list_callback",
    ]

    def __init__(
        self,
        url: str,
        content: str,
        recursion_level: int,
        web_client: AbstractWebClient,
        parent_urls: set[str],
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        self._url = url
        self._content = content
        self._recursion_level = recursion_level
        self._web_client = web_client
        self._parent_urls = parent_urls

        if recurse_callback is None:  # Always allow child recursion
            self._recurse_callback = lambda url, level, parent_urls: True
        else:
            self._recurse_callback = recurse_callback

        if recurse_list_callback is None:  # Always allow child recursion
            self._recurse_list_callback = lambda urls, level, parent_urls: urls
        else:
            self._recurse_list_callback = recurse_list_callback

    @abc.abstractmethod
    def sitemap(self) -> AbstractSitemap:
        """
        Create the parsed sitemap instance and perform any sub-parsing needed.

        :return: an instance of the appropriate sitemap class
        """
        raise NotImplementedError("Abstract method.")


class IndexRobotsTxtSitemapParser(AbstractSitemapParser):
    """robots.txt index sitemap parser."""

    def __init__(
        self,
        url: str,
        content: str,
        recursion_level: int,
        web_client: AbstractWebClient,
        parent_urls: set[str],
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        super().__init__(
            url=url,
            content=content,
            recursion_level=recursion_level,
            web_client=web_client,
            parent_urls=parent_urls,
            recurse_callback=recurse_callback,
            recurse_list_callback=recurse_list_callback,
        )

        if not self._url.endswith("/robots.txt"):
            raise SitemapException(
                f"URL does not look like robots.txt URL: {self._url}"
            )

    def sitemap(self) -> AbstractSitemap:
        # Serves as an ordered set because we want to deduplicate URLs but also retain the order
        sitemap_urls = OrderedDict()

        for robots_txt_line in self._content.splitlines():
            robots_txt_line = robots_txt_line.strip()
            # robots.txt is supposed to be case sensitive but who cares in these Node.js times?
            sitemap_match = re.search(
                r"^site-?map:\s*(.+?)$", robots_txt_line, flags=re.IGNORECASE
            )
            if sitemap_match:
                sitemap_url = sitemap_match.group(1)
                if is_http_url(sitemap_url):
                    sitemap_urls[sitemap_url] = True
                else:
                    log.warning(
                        f"Sitemap URL {sitemap_url} doesn't look like an URL, skipping"
                    )

        sub_sitemaps = []
        parent_urls = self._parent_urls | {self._url}

        filtered_sitemap_urls = self._recurse_list_callback(
            list(sitemap_urls.keys()), self._recursion_level, parent_urls
        )
        for sitemap_url in filtered_sitemap_urls:
            try:
                if self._recurse_callback(
                    sitemap_url, self._recursion_level, parent_urls
                ):
                    fetcher = SitemapFetcher(
                        url=sitemap_url,
                        recursion_level=self._recursion_level + 1,
                        web_client=self._web_client,
                        parent_urls=parent_urls,
                        recurse_callback=self._recurse_callback,
                        recurse_list_callback=self._recurse_list_callback,
                    )
                    fetched_sitemap = fetcher.sitemap()
                else:
                    continue
            except NoWebClientException:
                fetched_sitemap = InvalidSitemap(
                    url=sitemap_url, reason="Un-fetched child sitemap"
                )
            except Exception as ex:
                fetched_sitemap = InvalidSitemap(
                    url=sitemap_url,
                    reason=f"Unable to add sub-sitemap from URL {sitemap_url}: {str(ex)}",
                )
            sub_sitemaps.append(fetched_sitemap)

        index_sitemap = IndexRobotsTxtSitemap(url=self._url, sub_sitemaps=sub_sitemaps)

        return index_sitemap


class PlainTextSitemapParser(AbstractSitemapParser):
    """Plain text sitemap parser."""

    def sitemap(self) -> AbstractSitemap:
        story_urls = OrderedDict()

        for story_url in self._content.splitlines():
            story_url = story_url.strip()
            if not story_url:
                continue
            if is_http_url(story_url):
                story_urls[story_url] = True
            else:
                log.warning(f"Story URL {story_url} doesn't look like an URL, skipping")

        pages = []
        for page_url in story_urls.keys():
            page = SitemapPage(url=page_url)
            pages.append(page)

        text_sitemap = PagesTextSitemap(url=self._url, pages=pages)

        return text_sitemap


class XMLSitemapParser(AbstractSitemapParser):
    """Initial XML sitemap parser.

    Instantiates an Expat parser and registers handler methods, which determine the specific format
    and instantiates a concrete parser (inheriting from :class:`AbstractXMLSitemapParser`) to extract data.
    """

    __XML_NAMESPACE_SEPARATOR = " "

    __slots__ = [
        "_concrete_parser",
        "_is_non_ns_sitemap",
    ]

    def __init__(
        self,
        url: str,
        content: str,
        recursion_level: int,
        web_client: AbstractWebClient,
        parent_urls: set[str],
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        super().__init__(
            url=url,
            content=content,
            recursion_level=recursion_level,
            web_client=web_client,
            parent_urls=parent_urls,
            recurse_callback=recurse_callback,
            recurse_list_callback=recurse_list_callback,
        )

        # Will be initialized when the type of sitemap is known
        self._concrete_parser: AbstractXMLSitemapParser | None = None
        # Whether this is a malformed sitemap with no namespace
        self._is_non_ns_sitemap = False

    def sitemap(self) -> AbstractSitemap:
        parser = xml.parsers.expat.ParserCreate(
            namespace_separator=self.__XML_NAMESPACE_SEPARATOR
        )
        parser.StartElementHandler = self._xml_element_start
        parser.EndElementHandler = self._xml_element_end
        parser.CharacterDataHandler = self._xml_char_data

        try:
            is_final = True
            parser.Parse(self._content, is_final)
        except Exception as ex:
            # Some sitemap XML files might end abruptly because webservers might be timing out on returning huge XML
            # files so don't return InvalidSitemap() but try to get as much pages as possible
            log.error(f"Parsing sitemap from URL {self._url} failed: {ex}")

        if not self._concrete_parser:
            return InvalidSitemap(
                url=self._url,
                reason=f"No parsers support sitemap from {self._url}",
            )

        return self._concrete_parser.sitemap()

    def __normalize_xml_element_name(self, name: str):
        """
        Replace the namespace URL in the argument element name with internal namespace.

        * Elements from http://www.sitemaps.org/schemas/sitemap/0.9 namespace will be prefixed with "sitemap:",
          e.g. "<loc>" will become "<sitemap:loc>"

        * Elements from http://www.google.com/schemas/sitemap-news/0.9 namespace will be prefixed with "news:",
          e.g. "<publication>" will become "<news:publication>"

        For non-sitemap namespaces, return the element name with the namespace stripped.

        :param name: Namespace URL plus XML element name, e.g. "http://www.sitemaps.org/schemas/sitemap/0.9 loc"
        :return: Internal namespace name plus element name, e.g. "sitemap loc"
        """

        name_parts = name.split(self.__XML_NAMESPACE_SEPARATOR)

        if len(name_parts) == 1:
            namespace_url = ""
            name = name_parts[0]

        elif len(name_parts) == 2:
            namespace_url = name_parts[0]
            name = name_parts[1]

        else:
            raise SitemapXMLParsingException(
                f"Unable to determine namespace for element '{name}'"
            )

        if "/geo/schemas/sitemap/" in namespace_url:
            name = f"geo:{name}"
        elif "baidu.com/schemas/sitemap-mobile" in namespace_url:
            name = f"mobile:{name}"
        elif "codesearch/schemas/sitemap" in namespace_url:
            name = f"codesearch:{name}"
        elif "/sitemap-pagemap/" in namespace_url:
            name = f"pagemap:{name}"
        elif "sw.deri.org" in namespace_url and "scschema" in namespace_url:
            name = f"sc:{name}"
        elif "/sitemap/" in namespace_url:
            name = f"sitemap:{name}"
        elif "/sitemap-news/" in namespace_url:
            name = f"news:{name}"
        elif "/sitemap-image/" in namespace_url:
            name = f"image:{name}"
        elif "/sitemap-video/" in namespace_url:
            name = f"video:{name}"
        elif "search.yahoo.com/mrss" in namespace_url:
            name = f"media:{name}"
        elif "purl.org/dc/terms" in namespace_url:
            name = f"dcterms:{name}"
        elif name in {"urlset", "sitemapindex"}:
            # XML sitemap root tag but namespace is not set
            self._is_non_ns_sitemap = True
            log.warning(
                f'XML sitemap root tag {name} detected without expected xmlns (value is "{namespace_url}"), '
                f"assuming is an XML sitemap."
            )
            name = f"sitemap:{name}"
        elif self._is_non_ns_sitemap:
            # Flag has previously been set and no other namespace matched,
            # assume this should be in the sitemap namespace
            log.debug(f"Assuming {name} should be in sitemap namespace")
            name = f"sitemap:{name}"
        else:
            # We don't care about the rest of the namespaces, so just keep the plain element name
            pass

        return name

    def _xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        name = self.__normalize_xml_element_name(name)

        if self._concrete_parser:
            self._concrete_parser.xml_element_start(name=name, attrs=attrs)

        else:
            # Root element -- initialize concrete parser
            if name == "sitemap:urlset":
                self._concrete_parser = PagesXMLSitemapParser(
                    url=self._url,
                )

            elif name == "sitemap:sitemapindex":
                self._concrete_parser = IndexXMLSitemapParser(
                    url=self._url,
                    web_client=self._web_client,
                    recursion_level=self._recursion_level,
                    parent_urls=self._parent_urls,
                    recurse_callback=self._recurse_callback,
                    recurse_list_callback=self._recurse_list_callback,
                )

            elif name == "rss":
                self._concrete_parser = PagesRSSSitemapParser(
                    url=self._url,
                )

            elif name == "feed":
                self._concrete_parser = PagesAtomSitemapParser(
                    url=self._url,
                )

            elif name == "sc:dataset":
                self._concrete_parser = SemanticWebSitemapParser(
                    url=self._url,
                )

            else:
                raise SitemapXMLParsingException(f"Unsupported root element '{name}'.")

    def _xml_element_end(self, name: str) -> None:
        name = self.__normalize_xml_element_name(name)

        if not self._concrete_parser:
            raise SitemapXMLParsingException(
                "Concrete sitemap parser should be set by now."
            )

        self._concrete_parser.xml_element_end(name=name)

    def _xml_char_data(self, data: str) -> None:
        if not self._concrete_parser:
            raise SitemapXMLParsingException(
                "Concrete sitemap parser should be set by now."
            )

        self._concrete_parser.xml_char_data(data=data)


class AbstractXMLSitemapParser(metaclass=abc.ABCMeta):
    """
    Abstract XML sitemap parser.
    """

    __slots__ = [
        # URL of the sitemap that is being parsed
        "_url",
        # Last encountered character data
        "_last_char_data",
        "_last_handler_call_was_xml_char_data",
        "_recurse_callback",
        "_recurse_list_callback",
    ]

    def __init__(
        self,
        url: str,
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        self._url = url
        self._last_char_data = ""
        self._last_handler_call_was_xml_char_data = False

        if recurse_callback is None:  # Always allow child recursion
            self._recurse_callback = lambda url, level, parent_urls: True
        else:
            self._recurse_callback = recurse_callback

        if recurse_list_callback is None:  # Always allow child recursion
            self._recurse_list_callback = lambda urls, level, parent_urls: urls
        else:
            self._recurse_list_callback = recurse_list_callback

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        """Concrete parser handler when the start of an element is encountered.

        See :external+python:meth:`xmlparser.StartElementHandler <xml.parsers.expat.xmlparser.StartElementHandler>`

        :param name: element name, potentially prefixed with namespace
        :param attrs: element attributes
        """
        self._last_handler_call_was_xml_char_data = False
        pass

    def xml_element_end(self, name: str) -> None:
        """Concrete parser handler when the end of an element is encountered.

        See :external+python:meth:`xmlparser.EndElementHandler <xml.parsers.expat.xmlparser.EndElementHandler>`

        :param name: element name, potentially prefixed with namespace
        """
        # End of any element always resets last encountered character data
        self._last_char_data = ""
        self._last_handler_call_was_xml_char_data = False

    def xml_char_data(self, data: str) -> None:
        """
        Concrete parser handler for character data.

        Multiple concurrent calls are concatenated until an XML element start or end is reached,
        as it may be called multiple times for a single string.
        E.g. ``ABC &amp; DEF``.

        See :external+python:meth:`xmlparser.CharacterDataHandler <xml.parsers.expat.xmlparser.CharacterDataHandler>`

        :param data: string data
        """
        if self._last_handler_call_was_xml_char_data:
            self._last_char_data += data
        else:
            self._last_char_data = data

        self._last_handler_call_was_xml_char_data = True

    @abc.abstractmethod
    def sitemap(self) -> AbstractSitemap:
        """
        Create the parsed sitemap instance and perform any sub-parsing needed.

        :return: an instance of the appropriate sitemap class
        """
        raise NotImplementedError("Abstract method.")


class IndexXMLSitemapParser(AbstractXMLSitemapParser):
    """
    Index XML sitemap parser.
    """

    __slots__ = [
        "_web_client",
        "_recursion_level",
        # List of sub-sitemap URLs found in this index sitemap
        "_sub_sitemap_urls",
        "_parent_urls",
    ]

    def __init__(
        self,
        url: str,
        web_client: AbstractWebClient,
        recursion_level: int,
        parent_urls: set[str],
        recurse_callback: RecurseCallbackType | None = None,
        recurse_list_callback: RecurseListCallbackType | None = None,
    ):
        super().__init__(
            url=url,
            recurse_callback=recurse_callback,
            recurse_list_callback=recurse_list_callback,
        )

        self._web_client = web_client
        self._recursion_level = recursion_level
        self._sub_sitemap_urls: list[str] = []
        self._parent_urls = parent_urls

    def xml_element_end(self, name: str) -> None:
        if name == "sitemap:loc":
            sub_sitemap_url = html_unescape_strip(self._last_char_data)
            if not sub_sitemap_url or not is_http_url(sub_sitemap_url):
                log.warning(
                    f"Sub-sitemap URL does not look like one: {sub_sitemap_url}"
                )

            else:
                if sub_sitemap_url not in self._sub_sitemap_urls:
                    self._sub_sitemap_urls.append(sub_sitemap_url)

        super().xml_element_end(name=name)

    def sitemap(self) -> AbstractSitemap:
        sub_sitemaps = []

        parent_urls = self._parent_urls | {self._url}
        filtered_sitemap_urls = self._recurse_list_callback(
            list(self._sub_sitemap_urls), self._recursion_level, parent_urls
        )
        for sub_sitemap_url in filtered_sitemap_urls:
            # URL might be invalid, or recursion limit might have been reached
            try:
                if self._recurse_callback(
                    sub_sitemap_url, self._recursion_level, parent_urls
                ):
                    fetcher = SitemapFetcher(
                        url=sub_sitemap_url,
                        recursion_level=self._recursion_level + 1,
                        web_client=self._web_client,
                        parent_urls=parent_urls,
                        recurse_callback=self._recurse_callback,
                        recurse_list_callback=self._recurse_list_callback,
                    )
                    fetched_sitemap = fetcher.sitemap()
                else:
                    continue
            except NoWebClientException:
                fetched_sitemap = InvalidSitemap(
                    url=sub_sitemap_url, reason="Un-fetched child sitemap"
                )
            except Exception as ex:
                fetched_sitemap = InvalidSitemap(
                    url=sub_sitemap_url,
                    reason=f"Unable to add sub-sitemap from URL {sub_sitemap_url}: {str(ex)}",
                )

            sub_sitemaps.append(fetched_sitemap)

        return IndexXMLSitemap(url=self._url, sub_sitemaps=sub_sitemaps)


MIN_VALID_PRIORITY = Decimal("0.0")
MAX_VALID_PRIORITY = Decimal("1.0")


class PagesXMLSitemapParser(AbstractXMLSitemapParser):
    """
    Pages XML sitemap parser.
    """

    class Image:
        """Data class for holding image data while parsing."""

        __slots__ = ["loc", "caption", "geo_location", "title", "license"]

        def __init__(self):
            self.loc: str | None = None
            self.caption: str | None = None
            self.geo_location: str | None = None
            self.title: str | None = None
            self.license: str | None = None

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL to be able to find unique ones
                    self.loc,
                )
            )

    class Video:
        """Data class for holding video data while parsing."""

        __slots__ = [
            "thumbnail_loc",
            "title",
            "description",
            "content_loc",
            "player_loc",
            "duration",
            "expiration_date",
            "rating",
            "view_count",
            "publication_date",
            "family_friendly",
            "restriction",
            "restriction_relationship",
            "platform",
            "platform_relationship",
            "requires_subscription",
            "uploader",
            "uploader_info",
            "live",
            "tags",
            "prices",
            "dcterms_valid",
        ]

        def __init__(self):
            self.thumbnail_loc: str | None = None
            self.title: str | None = None
            self.description: str | None = None
            self.content_loc: str | None = None
            self.player_loc: str | None = None
            self.duration: str | None = None
            self.expiration_date: str | None = None
            self.rating: str | None = None
            self.view_count: str | None = None
            self.publication_date: str | None = None
            self.family_friendly: str | None = None
            self.restriction: str | None = None
            self.restriction_relationship: str | None = None
            self.platform: str | None = None
            self.platform_relationship: str | None = None
            self.requires_subscription: str | None = None
            self.uploader: str | None = None
            self.uploader_info: str | None = None
            self.live: str | None = None
            self.tags: list[str] = []
            self.prices: list[SitemapVideoPrice] = []
            self.dcterms_valid: str | None = None

        def __hash__(self):
            return hash(
                (
                    self.thumbnail_loc,
                    self.title,
                    self.description,
                    self.content_loc,
                    self.player_loc,
                )
            )

    class DataObject:
        """Data class for holding PageMap DataObject data while parsing."""

        __slots__ = ["type", "id", "attributes"]

        def __init__(self):
            self.type: str | None = None
            self.id: str | None = None
            self.attributes: list[tuple[str, str]] = []

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
            "mobile_type",
            "geo_format",
            "handheld",
            "page_map_objects",
            "codesearch_filetype",
            "codesearch_license",
            "codesearch_filename",
            "codesearch_packageurl",
            "codesearch_packagemap",
        ]

        def __init__(self):
            self.url: str | None = None
            self.last_modified: str | None = None
            self.change_frequency: str | None = None
            self.priority: str | None = None
            self.news_title: str | None = None
            self.news_publish_date: str | None = None
            self.news_publication_name: str | None = None
            self.news_publication_language: str | None = None
            self.news_access: str | None = None
            self.news_genres: str | None = None
            self.news_keywords: str | None = None
            self.news_stock_tickers: str | None = None
            self.images: list[PagesXMLSitemapParser.Image] = []
            self.videos: list[PagesXMLSitemapParser.Video] = []
            self.alternates: list[tuple[str, str]] = []
            self.mobile_type: str | None = None
            self.geo_format: str | None = None
            self.handheld: str | None = None
            self.page_map_objects: list[PagesXMLSitemapParser.DataObject] | None = None
            self.codesearch_filetype: str | None = None
            self.codesearch_license: str | None = None
            self.codesearch_filename: str | None = None
            self.codesearch_packageurl: str | None = None
            self.codesearch_packagemap: str | None = None

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL to be able to find unique ones
                    self.url,
                )
            )

        def page(self) -> SitemapPage | None:
            """Return constructed sitemap page if one has been completed, otherwise None."""

            # Required
            url = html_unescape_strip(self.url)
            if not url:
                log.error("URL is unset")
                return None

            last_modified_raw = html_unescape_strip(self.last_modified)
            last_modified: datetime.datetime | None = None
            if last_modified_raw:
                last_modified = parse_iso8601_date(last_modified_raw)

            change_frequency_raw = html_unescape_strip(self.change_frequency)
            change_frequency: SitemapPageChangeFrequency | None = None
            if change_frequency_raw:
                change_frequency_raw = change_frequency_raw.lower()
                if SitemapPageChangeFrequency.has_value(change_frequency_raw):
                    change_frequency = SitemapPageChangeFrequency(change_frequency_raw)
                else:
                    log.warning(
                        "Invalid change frequency, defaulting to 'always'.".format()
                    )
                    change_frequency = SitemapPageChangeFrequency.ALWAYS

            priority_raw = html_unescape_strip(self.priority)
            priority: Decimal = SITEMAP_PAGE_DEFAULT_PRIORITY
            if priority_raw:
                try:
                    priority = Decimal(priority_raw)

                    if priority < MIN_VALID_PRIORITY or priority > MAX_VALID_PRIORITY:
                        log.warning(f"Priority is not within 0 and 1: {priority}")
                        priority = SITEMAP_PAGE_DEFAULT_PRIORITY
                except InvalidOperation:
                    log.warning(f"Invalid priority: {priority_raw}")
                    priority = SITEMAP_PAGE_DEFAULT_PRIORITY

            news_title = html_unescape_strip(self.news_title)

            news_publish_date_raw = html_unescape_strip(self.news_publish_date)
            news_publish_date: datetime.datetime | None = None
            if news_publish_date_raw:
                news_publish_date = parse_iso8601_date(
                    date_string=news_publish_date_raw
                )

            news_publication_name = html_unescape_strip(self.news_publication_name)
            news_publication_language = html_unescape_strip(
                self.news_publication_language
            )
            news_access = html_unescape_strip(self.news_access)

            news_genres_raw = html_unescape_strip(self.news_genres)
            news_genres: list[str] = []
            if news_genres_raw:
                news_genres = [x.strip() for x in news_genres_raw.split(",")]

            news_keywords_raw = html_unescape_strip(self.news_keywords)
            news_keywords: list[str] = []
            if news_keywords_raw:
                news_keywords = [x.strip() for x in news_keywords_raw.split(",")]

            news_stock_tickers_raw = html_unescape_strip(self.news_stock_tickers)
            news_stock_tickers: list[str] = []
            if news_stock_tickers_raw:
                news_stock_tickers = [
                    x.strip() for x in news_stock_tickers_raw.split(",")
                ]

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
                    if image.loc
                ]

            sitemap_videos = None
            if len(self.videos) > 0:
                parsed_videos = []
                for video in self.videos:
                    duration_raw = html_unescape_strip(video.duration)
                    duration: int | None = None
                    if duration_raw:
                        try:
                            duration = int(duration_raw)
                        except ValueError:
                            duration = None

                    expiration_date_raw = html_unescape_strip(video.expiration_date)
                    expiration_date: datetime.datetime | None = None
                    if expiration_date_raw:
                        expiration_date = parse_iso8601_date(expiration_date_raw)

                    rating_raw = html_unescape_strip(video.rating)
                    rating: Decimal | str | None = None
                    if rating_raw:
                        try:
                            rating = Decimal(rating_raw)
                        except InvalidOperation:
                            rating = rating_raw

                    view_count_raw = html_unescape_strip(video.view_count)
                    view_count: int | None = None
                    if view_count_raw:
                        try:
                            view_count = int(view_count_raw)
                        except ValueError:
                            view_count = None

                    publication_date_raw = html_unescape_strip(video.publication_date)
                    publication_date: datetime.datetime | None = None
                    if publication_date_raw:
                        publication_date = parse_iso8601_date(publication_date_raw)

                    restriction_raw = html_unescape_strip(video.restriction)
                    restriction: SitemapVideoRestriction | None = None
                    if restriction_raw:
                        restriction = (
                            video.restriction_relationship,
                            tuple([x for x in restriction_raw.split(" ") if x]),
                        )

                    platform_raw = html_unescape_strip(video.platform)
                    platform: SitemapVideoRestriction | None = None
                    if platform_raw:
                        platform = (
                            video.platform_relationship,
                            tuple([x for x in platform_raw.split(" ") if x]),
                        )

                    parsed_video = SitemapVideo(
                        thumbnail_loc=html_unescape_strip(video.thumbnail_loc),
                        title=html_unescape_strip(video.title),
                        description=html_unescape_strip(video.description),
                        content_loc=html_unescape_strip(video.content_loc),
                        player_loc=html_unescape_strip(video.player_loc),
                        duration=duration,
                        expiration_date=expiration_date,
                        rating=rating,
                        view_count=view_count,
                        publication_date=publication_date,
                        family_friendly=html_unescape_strip(video.family_friendly),
                        restriction=restriction,
                        platform=platform,
                        requires_subscription=html_unescape_strip(
                            video.requires_subscription
                        ),
                        uploader=html_unescape_strip(video.uploader),
                        uploader_info=html_unescape_strip(video.uploader_info),
                        live=html_unescape_strip(video.live),
                        tags=[
                            t
                            for t in [html_unescape_strip(x) for x in video.tags]
                            if t
                        ],
                        prices=video.prices,
                        dcterms_valid=html_unescape_strip(video.dcterms_valid),
                    )
                    parsed_videos.append(parsed_video)

                if len(parsed_videos) > 0:
                    sitemap_videos = parsed_videos

            alternates = None
            if len(self.alternates) > 0:
                alternates = self.alternates

            mobile = None
            if self.mobile_type:
                mobile = SitemapMobile(type=self.mobile_type)

            geo = None
            if self.geo_format:
                geo = SitemapGeo(format=self.geo_format)

            page_map = None
            if self.page_map_objects is not None:
                page_map = SitemapPageMap(
                    data_objects=[
                        SitemapPageMapDataObject(
                            type=obj.type,
                            id=obj.id,
                            attributes=[
                                SitemapPageMapAttribute(name=n, value=v)
                                for n, v in obj.attributes
                            ],
                        )
                        for obj in self.page_map_objects
                    ]
                )

            code_search = None
            if any(
                [
                    self.codesearch_filetype,
                    self.codesearch_license,
                    self.codesearch_filename,
                    self.codesearch_packageurl,
                    self.codesearch_packagemap,
                ]
            ):
                code_search = SitemapCodeSearch(
                    filetype=self.codesearch_filetype,
                    license=self.codesearch_license,
                    filename=self.codesearch_filename,
                    packageurl=self.codesearch_packageurl,
                    packagemap=self.codesearch_packagemap,
                )

            return SitemapPage(
                url=url,
                last_modified=last_modified,
                change_frequency=change_frequency,
                priority=priority,
                news_story=sitemap_news_story,
                images=sitemap_images,
                videos=sitemap_videos,
                alternates=alternates,
                mobile=mobile,
                geo=geo,
                handheld=self.handheld,
                page_map=page_map,
                code_search=code_search,
            )

    __slots__ = [
        "_current_page",
        "_pages",
        "_page_urls",
        "_current_image",
        "_current_video",
        "_current_data_object",
        "_current_attribute_name",
    ]

    def __init__(self, url: str):
        super().__init__(url=url)

        self._current_page: PagesXMLSitemapParser.Page | None = None
        self._pages: list[PagesXMLSitemapParser.Page] = []
        self._page_urls: set[str] = set()
        self._current_image: PagesXMLSitemapParser.Image | None = None
        self._current_video: PagesXMLSitemapParser.Video | None = None
        self._current_data_object: PagesXMLSitemapParser.DataObject | None = None
        self._current_attribute_name: str | None = None

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        super().xml_element_start(name=name, attrs=attrs)

        if name == "sitemap:url":
            if self._current_page:
                log.warning("Ignoring incomplete <url> entry before starting a new one.")
            self._current_page = self.Page()
        elif name == "image:image":
            if self._current_image:
                log.warning("Ignoring nested <image:image> start.")
                return
            if not self._current_page:
                log.warning("Skipping <image:image> outside <url>.")
                return
            self._current_image = self.Image()
        elif name == "video:video":
            if self._current_video:
                log.warning("Ignoring nested <video:video> start.")
                return
            if not self._current_page:
                log.warning("Skipping <video:video> outside <url>.")
                return
            self._current_video = self.Video()
        elif name == "video:restriction":
            if self._current_video:
                self._current_video.restriction_relationship = attrs.get(
                    "relationship"
                )
        elif name == "video:platform":
            if self._current_video:
                self._current_video.platform_relationship = attrs.get(
                    "relationship"
                )
        elif name == "video:uploader":
            if self._current_video:
                self._current_video.uploader_info = attrs.get("info")
        elif name == "video:price":
            if self._current_video:
                self._current_video.prices.append(
                    (
                        None,
                        attrs.get("currency"),
                        attrs.get("type"),
                        attrs.get("info"),
                    )
                )
        elif name == "mobile:mobile":
            if not self._current_page:
                log.warning("Skipping <mobile:mobile> outside <url>.")
                return
            self._current_page.mobile_type = attrs.get("type")
        elif name == "link":
            if not self._current_page:
                log.warning("Skipping <link> outside <url>.")
                return
            if "rel" not in attrs or attrs["rel"] != "alternate":
                log.warning(f"<link> element is missing rel attribute: {attrs}.")
            elif attrs.get("media") == "handheld" and "href" in attrs:
                self._current_page.handheld = attrs["href"]
            elif "hreflang" not in attrs or "href" not in attrs:
                log.warning(
                    f"<link> element is missing hreflang or href attributes: {attrs}."
                )
            else:
                self._current_page.alternates.append((attrs["hreflang"], attrs["href"]))
        elif name == "pagemap:PageMap":
            if not self._current_page:
                log.warning("Skipping <pagemap:PageMap> outside <url>.")
                return
            self._current_page.page_map_objects = []
        elif name == "pagemap:DataObject":
            if not self._current_page or self._current_page.page_map_objects is None:
                log.warning("Skipping <pagemap:DataObject> outside <pagemap:PageMap>.")
                return
            self._current_data_object = self.DataObject()
            self._current_data_object.type = attrs.get("type")
            self._current_data_object.id = attrs.get("id")
        elif name == "pagemap:Attribute":
            if self._current_data_object is None:
                log.warning("Skipping <pagemap:Attribute> outside <pagemap:DataObject>.")
                return
            self._current_attribute_name = attrs.get("name")

    def __require_last_char_data_to_be_set(self, name: str) -> None:
        if not self._last_char_data:
            raise SitemapXMLParsingException(
                f"Character data is expected to be set at the end of <{name}>."
            )

    def xml_element_end(self, name: str) -> None:
        if not self._current_page and name != "sitemap:urlset":
            log.debug(f"Skipping <{name}> outside <url>.")
            super().xml_element_end(name=name)
            return

        if name == "sitemap:url":
            if self._current_page and self._current_page.url and self._current_page.url not in self._page_urls:
                self._pages.append(self._current_page)
                self._page_urls.add(self._current_page.url)
            elif self._current_page and not self._current_page.url:
                log.debug("Skipping malformed <url> entry because URL is unset.")
            self._current_page = None
        elif name == "image:image":
            if self._current_page and self._current_image:
                self._current_page.images.append(self._current_image)
            self._current_image = None
        elif name == "video:video":
            if self._current_page and self._current_video:
                self._current_page.videos.append(self._current_video)
            self._current_video = None
        else:
            assert self._current_page is not None
            if name == "sitemap:loc":
                # Every entry should have <loc>, skip malformed rows when missing.
                if self._last_char_data:
                    self._current_page.url = self._last_char_data
                else:
                    log.warning("Skipping empty <sitemap:loc> in <url> entry.")

            elif name == "sitemap:lastmod":
                # Element might be present but character data might be empty
                self._current_page.last_modified = self._last_char_data

            elif name == "sitemap:changefreq":
                # Element might be present but character data might be empty
                self._current_page.change_frequency = self._last_char_data

            elif name == "sitemap:priority":
                # Element might be present but character data might be empty
                self._current_page.priority = self._last_char_data

            elif name == "news:name":  # news/publication/name
                # Element might be present but character data might be empty
                self._current_page.news_publication_name = self._last_char_data

            elif name == "news:language":  # news/publication/language
                # Element might be present but character data might be empty
                self._current_page.news_publication_language = self._last_char_data

            elif name == "news:publication_date":
                # Element might be present but character data might be empty
                self._current_page.news_publish_date = self._last_char_data

            elif name == "news:title":
                # Title is required for valid news entries, but tolerate malformed rows.
                if self._last_char_data:
                    self._current_page.news_title = self._last_char_data
                else:
                    log.warning("Skipping empty <news:title>.")

            elif name == "news:access":
                # Element might be present but character data might be empty
                self._current_page.news_access = self._last_char_data

            elif name == "news:keywords":
                # Element might be present but character data might be empty
                self._current_page.news_keywords = self._last_char_data

            elif name == "news:stock_tickers":
                # Element might be present but character data might be empty
                self._current_page.news_stock_tickers = self._last_char_data

            elif name == "image:loc":
                # Every image entry should have <loc>, but tolerate malformed entries.
                if self._current_image and self._last_char_data:
                    self._current_image.loc = self._last_char_data
                else:
                    log.warning("Skipping malformed <image:loc>.")

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

            elif name == "video:thumbnail_loc":
                if self._current_video and self._last_char_data:
                    self._current_video.thumbnail_loc = self._last_char_data
                else:
                    log.warning("Skipping malformed <video:thumbnail_loc>.")

            elif name == "video:title":
                if self._current_video and self._last_char_data:
                    self._current_video.title = self._last_char_data
                else:
                    log.warning("Skipping malformed <video:title>.")

            elif name == "video:description":
                if self._current_video and self._last_char_data:
                    self._current_video.description = self._last_char_data
                else:
                    log.warning("Skipping malformed <video:description>.")

            elif name == "video:content_loc":
                if self._current_video and self._last_char_data:
                    self._current_video.content_loc = self._last_char_data
                else:
                    log.warning("Skipping malformed <video:content_loc>.")

            elif name == "video:player_loc":
                if self._current_video and self._last_char_data:
                    self._current_video.player_loc = self._last_char_data
                else:
                    log.warning("Skipping malformed <video:player_loc>.")

            elif name == "video:duration":
                if self._current_video:
                    self._current_video.duration = self._last_char_data

            elif name == "video:expiration_date":
                if self._current_video:
                    self._current_video.expiration_date = self._last_char_data

            elif name == "video:rating":
                if self._current_video:
                    self._current_video.rating = self._last_char_data

            elif name == "video:view_count":
                if self._current_video:
                    self._current_video.view_count = self._last_char_data

            elif name == "video:publication_date":
                if self._current_video:
                    self._current_video.publication_date = self._last_char_data

            elif name == "video:family_friendly":
                if self._current_video:
                    self._current_video.family_friendly = self._last_char_data

            elif name == "video:restriction":
                if self._current_video:
                    self._current_video.restriction = self._last_char_data

            elif name == "video:platform":
                if self._current_video:
                    self._current_video.platform = self._last_char_data

            elif name == "video:requires_subscription":
                if self._current_video:
                    self._current_video.requires_subscription = self._last_char_data

            elif name == "video:uploader":
                if self._current_video:
                    self._current_video.uploader = self._last_char_data

            elif name == "video:live":
                if self._current_video:
                    self._current_video.live = self._last_char_data

            elif name == "video:tag":
                if self._current_video:
                    self._current_video.tags.append(self._last_char_data)

            elif name == "geo:format":
                if self._current_page:
                    self._current_page.geo_format = self._last_char_data

            elif name == "pagemap:Attribute":
                if self._current_data_object is not None and self._current_attribute_name:
                    self._current_data_object.attributes.append(
                        (self._current_attribute_name, self._last_char_data or "")
                    )
                self._current_attribute_name = None

            elif name == "pagemap:DataObject":
                if self._current_page and self._current_page.page_map_objects is not None and self._current_data_object is not None:
                    self._current_page.page_map_objects.append(self._current_data_object)
                self._current_data_object = None

            elif name == "codesearch:filetype":
                if self._current_page:
                    self._current_page.codesearch_filetype = self._last_char_data

            elif name == "codesearch:license":
                if self._current_page:
                    self._current_page.codesearch_license = self._last_char_data

            elif name == "codesearch:filename":
                if self._current_page:
                    self._current_page.codesearch_filename = self._last_char_data

            elif name == "codesearch:packageurl":
                if self._current_page:
                    self._current_page.codesearch_packageurl = self._last_char_data

            elif name == "codesearch:packagemap":
                if self._current_page:
                    self._current_page.codesearch_packagemap = self._last_char_data

        super().xml_element_end(name=name)

    def sitemap(self) -> AbstractSitemap:
        pages = []

        for page_row in self._pages:
            page = page_row.page()
            if page:
                pages.append(page)

        pages_sitemap = PagesXMLSitemap(url=self._url, pages=pages)

        return pages_sitemap


class PagesRSSSitemapParser(AbstractXMLSitemapParser):
    """
    Pages RSS 2.0 sitemap parser.

    https://validator.w3.org/feed/docs/rss2.html
    """

    class Page:
        """
        Data class for holding various properties for a single RSS <item> while parsing.
        """

        __slots__ = [
            "link",
            "title",
            "description",
            "publication_date",
            "media_content_url",
            "media_duration",
            "media_thumbnail_url",
            "media_player_url",
            "media_title",
            "media_description",
            "media_rating",
            "media_restriction",
            "media_restriction_relationship",
            "media_keywords",
            "media_category",
            "media_prices",
            "media_credit",
            "dcterms_valid",
        ]

        def __init__(self):
            self.link: str | None = None
            self.title: str | None = None
            self.description: str | None = None
            self.publication_date: str | None = None
            self.media_content_url: str | None = None
            self.media_duration: str | None = None
            self.media_thumbnail_url: str | None = None
            self.media_player_url: str | None = None
            self.media_title: str | None = None
            self.media_description: str | None = None
            self.media_rating: str | None = None
            self.media_restriction: str | None = None
            self.media_restriction_relationship: str | None = None
            self.media_keywords: str | None = None
            self.media_category: str | None = None
            self.media_prices: list[SitemapVideoPrice] = []
            self.media_credit: str | None = None
            self.dcterms_valid: str | None = None

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL
                    self.link,
                )
            )

        def page(self) -> SitemapPage | None:
            """Return constructed sitemap page if one has been completed, otherwise None."""

            # Required
            link = html_unescape_strip(self.link)
            if not link:
                log.error("Link is unset")
                return None

            title = html_unescape_strip(self.title)
            description = html_unescape_strip(self.description)
            if not (title or description):
                log.error("Both title and description are unset")
                return None

            publication_date_raw = html_unescape_strip(self.publication_date)
            publication_date: datetime.datetime | None = None
            if publication_date_raw:
                publication_date = parse_rfc2822_date(publication_date_raw)
            if publication_date is None:
                log.error("Publication date is unset")
                return None

            media_duration_raw = html_unescape_strip(self.media_duration)
            media_duration: int | None = None
            if media_duration_raw:
                try:
                    media_duration = int(media_duration_raw)
                except ValueError:
                    media_duration = None

            media_rating_raw = html_unescape_strip(self.media_rating)
            media_rating: Decimal | str | None = None
            if media_rating_raw:
                try:
                    media_rating = Decimal(media_rating_raw)
                except InvalidOperation:
                    media_rating = media_rating_raw

            media_restriction_raw = html_unescape_strip(self.media_restriction)
            media_restriction: SitemapVideoRestriction | None = None
            if media_restriction_raw:
                media_restriction = (
                    self.media_restriction_relationship,
                    tuple([x for x in media_restriction_raw.split(" ") if x]),
                )

            media_tags = []
            media_keywords = html_unescape_strip(self.media_keywords)
            if media_keywords:
                media_tags.extend([x.strip() for x in media_keywords.split(",") if x])
            media_category = html_unescape_strip(self.media_category)
            if media_category:
                media_tags.append(media_category)

            expiration_date = None
            dcterms_valid = html_unescape_strip(self.dcterms_valid)
            if dcterms_valid:
                end_match = re.search(r"(?:^|;)\s*end\s*=\s*([^;]+)", dcterms_valid)
                if end_match:
                    expiration_date = parse_iso8601_date(end_match.group(1).strip())

            sitemap_videos = None
            if any(
                [
                    self.media_content_url,
                    self.media_player_url,
                    self.media_title,
                    self.media_description,
                    self.media_thumbnail_url,
                ]
            ):
                sitemap_videos = [
                    SitemapVideo(
                        thumbnail_loc=html_unescape_strip(self.media_thumbnail_url),
                        title=html_unescape_strip(self.media_title),
                        description=html_unescape_strip(self.media_description),
                        content_loc=html_unescape_strip(self.media_content_url),
                        player_loc=html_unescape_strip(self.media_player_url),
                        duration=media_duration,
                        expiration_date=expiration_date,
                        rating=media_rating,
                        publication_date=publication_date,
                        restriction=media_restriction,
                        uploader=html_unescape_strip(self.media_credit),
                        tags=media_tags,
                        prices=self.media_prices,
                        dcterms_valid=dcterms_valid,
                    )
                ]

            news_title = title if title is not None else description
            assert news_title is not None

            return SitemapPage(
                url=link,
                news_story=SitemapNewsStory(
                    title=news_title,
                    publish_date=publication_date,
                ),
                videos=sitemap_videos,
            )

    __slots__ = ["_current_page", "_pages", "_page_links"]

    def __init__(self, url: str):
        super().__init__(url=url)

        self._current_page: PagesRSSSitemapParser.Page | None = None
        self._pages: list[PagesRSSSitemapParser.Page] = []
        self._page_links: set[str] = set()

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        super().xml_element_start(name=name, attrs=attrs)

        if name == "item":
            if self._current_page:
                raise SitemapXMLParsingException(
                    "Page is expected to be unset by <item>."
                )
            self._current_page = self.Page()
        elif self._current_page and name == "media:content":
            self._current_page.media_content_url = attrs.get("url")
            self._current_page.media_duration = attrs.get("duration")
        elif self._current_page and name == "media:thumbnail":
            self._current_page.media_thumbnail_url = attrs.get("url")
        elif self._current_page and name == "media:player":
            self._current_page.media_player_url = attrs.get("url")
        elif self._current_page and name == "media:restriction":
            self._current_page.media_restriction_relationship = attrs.get(
                "relationship"
            )
        elif self._current_page and name == "media:price":
            self._current_page.media_prices.append(
                (
                    None,
                    attrs.get("currency"),
                    attrs.get("type"),
                    attrs.get("info"),
                )
            )

    def __require_last_char_data_to_be_set(self, name: str) -> None:
        if not self._last_char_data:
            raise SitemapXMLParsingException(
                f"Character data is expected to be set at the end of <{name}>."
            )

    def xml_element_end(self, name: str) -> None:
        # If within <item> already
        if self._current_page:
            if name == "item":
                if self._current_page.link and self._current_page.link not in self._page_links:
                    self._pages.append(self._current_page)
                    self._page_links.add(self._current_page.link)
                self._current_page = None

            else:
                if name == "link":
                    # Every entry must have <link>
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.link = self._last_char_data

                elif name == "title":
                    # Title (if set) can't be empty
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.title = self._last_char_data

                elif name == "description":
                    # Description (if set) can't be empty
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.description = self._last_char_data

                elif name == "pubDate":
                    # Element might be present but character data might be empty
                    self._current_page.publication_date = self._last_char_data

                elif name == "media:title":
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.media_title = self._last_char_data

                elif name == "media:description":
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.media_description = self._last_char_data

                elif name == "media:rating":
                    self._current_page.media_rating = self._last_char_data

                elif name == "media:restriction":
                    self._current_page.media_restriction = self._last_char_data

                elif name == "media:keywords":
                    self._current_page.media_keywords = self._last_char_data

                elif name == "media:category":
                    self._current_page.media_category = self._last_char_data

                elif name == "media:credit":
                    self._current_page.media_credit = self._last_char_data

                elif name == "media:price":
                    if len(self._current_page.media_prices) > 0:
                        last_price = self._current_page.media_prices[-1]
                        self._current_page.media_prices[-1] = (
                            self._last_char_data,
                            last_price[1],
                            last_price[2],
                            last_price[3],
                        )

                elif name == "dcterms:valid":
                    self._current_page.dcterms_valid = self._last_char_data

        super().xml_element_end(name=name)

    def sitemap(self) -> AbstractSitemap:
        pages = []

        for page_row in self._pages:
            page = page_row.page()
            if page:
                pages.append(page)

        pages_sitemap = PagesRSSSitemap(url=self._url, pages=pages)

        return pages_sitemap


class PagesAtomSitemapParser(AbstractXMLSitemapParser):
    """
    Pages Atom 0.3 / 1.0 sitemap parser.

    References:

    - https://github.com/simplepie/simplepie-ng/wiki/Spec:-Atom-0.3
    - https://www.ietf.org/rfc/rfc4287.txt
    - http://rakaz.nl/2005/07/moving-from-atom-03-to-10.html
    """

    # FIXME merge with RSS parser class as there are too many similarities

    class Page:
        """Data class for holding various properties for a single Atom <entry> while parsing."""

        __slots__ = [
            "link",
            "title",
            "description",
            "publication_date",
        ]

        def __init__(self):
            self.link: str | None = None
            self.title: str | None = None
            self.description: str | None = None
            self.publication_date: str | None = None

        def __hash__(self):
            return hash(
                (
                    # Hash only the URL
                    self.link,
                )
            )

        def page(self) -> SitemapPage | None:
            """Return constructed sitemap page if one has been completed, otherwise None."""

            # Required
            link = html_unescape_strip(self.link)
            if not link:
                log.error("Link is unset")
                return None

            title = html_unescape_strip(self.title)
            description = html_unescape_strip(self.description)
            if not (title or description):
                log.error("Both title and description are unset")
                return None

            publication_date_raw = html_unescape_strip(self.publication_date)
            publication_date: datetime.datetime | None = None
            if publication_date_raw:
                publication_date = parse_iso8601_date(publication_date_raw)
            if publication_date is None:
                log.error("Publication date is unset")
                return None

            news_title = title if title is not None else description
            assert news_title is not None

            return SitemapPage(
                url=link,
                news_story=SitemapNewsStory(
                    title=news_title,
                    publish_date=publication_date,
                ),
            )

    __slots__ = [
        "_current_page",
        "_pages",
        "_page_links",
        "_last_link_rel_self_href",
    ]

    def __init__(self, url: str):
        super().__init__(url=url)

        self._current_page: PagesAtomSitemapParser.Page | None = None
        self._pages: list[PagesAtomSitemapParser.Page] = []
        self._page_links: set[str] = set()
        self._last_link_rel_self_href: str | None = None

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        super().xml_element_start(name=name, attrs=attrs)

        if name == "entry":
            if self._current_page:
                raise SitemapXMLParsingException(
                    "Page is expected to be unset by <entry>."
                )
            self._current_page = self.Page()

        elif name == "link":
            if self._current_page:
                if (
                    attrs.get("rel", "self").lower() == "self"
                    or self._last_link_rel_self_href is None
                ):
                    self._last_link_rel_self_href = attrs.get("href")

    def __require_last_char_data_to_be_set(self, name: str) -> None:
        if not self._last_char_data:
            raise SitemapXMLParsingException(
                f"Character data is expected to be set at the end of <{name}>."
            )

    def xml_element_end(self, name: str) -> None:
        # If within <entry> already
        if self._current_page:
            if name == "entry":
                if self._last_link_rel_self_href:
                    self._current_page.link = self._last_link_rel_self_href
                    self._last_link_rel_self_href = None

                    if self._current_page.link and self._current_page.link not in self._page_links:
                        self._pages.append(self._current_page)
                        self._page_links.add(self._current_page.link)

                self._current_page = None

            else:
                if name == "title":
                    # Title (if set) can't be empty
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.title = self._last_char_data

                elif name == "tagline" or name == "summary":
                    # Description (if set) can't be empty
                    self.__require_last_char_data_to_be_set(name=name)
                    self._current_page.description = self._last_char_data

                elif name == "issued" or name == "published":
                    # Element might be present but character data might be empty
                    self._current_page.publication_date = self._last_char_data

                elif name == "updated":
                    # No 'issued' or 'published' were set before
                    if not self._current_page.publication_date:
                        self._current_page.publication_date = self._last_char_data

        super().xml_element_end(name=name)

    def sitemap(self) -> AbstractSitemap:
        pages = []

        for page_row in self._pages:
            page = page_row.page()
            if page:
                pages.append(page)

        pages_sitemap = PagesAtomSitemap(url=self._url, pages=pages)

        return pages_sitemap


class SemanticWebSitemapParser(AbstractXMLSitemapParser):
    """
    Parser for Semantic Web (RDF) sitemaps using the SC (Semantic Crawling) extension.
    These sitemaps describe RDF datasets and their access methods at the dataset level,
    not at the individual page level.
    """

    class Dataset:
        """Temporary state holder for dataset parsing."""

        __slots__ = [
            "label",
            "dataset_uri",
            "linked_data_prefixes",
            "sparql_endpoint",
            "data_dump_locations",
            "sample_uris",
            "last_modified",
            "change_frequency",
        ]

        def __init__(self):
            self.label: str | None = None
            self.dataset_uri: str | None = None
            self.linked_data_prefixes: list[SitemapSemanticWebLinkedDataPrefix] = []
            self.sparql_endpoint: SitemapSemanticWebSparqlEndpoint | None = None
            self.data_dump_locations: list[str] = []
            self.sample_uris: list[str] = []
            self.last_modified: str | None = None
            self.change_frequency: str | None = None

    class Prefix:
        """Temporary state holder for linked data prefix parsing."""

        __slots__ = ["namespace", "prefix_value", "slice_method_name"]

        def __init__(self):
            self.namespace: str | None = None
            self.prefix_value: str | None = None
            self.slice_method_name: str | None = None

    class Endpoint:
        """Temporary state holder for SPARQL endpoint parsing."""

        __slots__ = ["location", "graph_name", "slice_method_name"]

        def __init__(self):
            self.location: str | None = None
            self.graph_name: str | None = None
            self.slice_method_name: str | None = None

    def __init__(self, url: str):
        super().__init__(url=url)
        self._current_dataset: SemanticWebSitemapParser.Dataset | None = self.Dataset()
        self._current_prefix: SemanticWebSitemapParser.Prefix | None = None
        self._current_endpoint: SemanticWebSitemapParser.Endpoint | None = None
        self._datasets: list[SitemapSemanticWebDataset] = []

    def xml_element_start(self, name: str, attrs: dict[str, str]) -> None:
        super().xml_element_start(name=name, attrs=attrs)
        self._last_char_data = ""

        if name == "sc:dataset":
            if self._current_dataset:
                raise SitemapXMLParsingException(
                    "Dataset is expected to be unset by <sc:dataset>."
                )
            self._current_dataset = self.Dataset()

        elif name == "sc:linkedDataPrefix" and self._current_dataset:
            if self._current_prefix:
                raise SitemapXMLParsingException(
                    "Prefix is expected to be unset by <sc:linkedDataPrefix>."
                )
            self._current_prefix = self.Prefix()
            # Check for optional slicing method
            if "sliceMethod" in attrs:
                self._current_prefix.slice_method_name = attrs["sliceMethod"]

        elif name == "sc:sparqlEndpointLocation" and self._current_dataset:
            if self._current_endpoint:
                raise SitemapXMLParsingException(
                    "Endpoint is expected to be unset by <sc:sparqlEndpointLocation>."
                )
            self._current_endpoint = self.Endpoint()
            # Check for optional slicing method
            if "sliceMethod" in attrs:
                self._current_endpoint.slice_method_name = attrs["sliceMethod"]

    def xml_element_end(self, name: str) -> None:
        if self._current_dataset:
            if name == "sc:dataset":
                # Build the final SitemapSemanticWebDataset object
                dataset = SitemapSemanticWebDataset(
                    label=self._current_dataset.label,
                    dataset_uri=self._current_dataset.dataset_uri,
                    linked_data_prefixes=self._current_dataset.linked_data_prefixes,
                    sparql_endpoint=self._current_dataset.sparql_endpoint,
                    data_dump_locations=self._current_dataset.data_dump_locations,
                    sample_uris=self._current_dataset.sample_uris,
                    last_modified=self._current_dataset.last_modified,
                    change_frequency=self._current_dataset.change_frequency,
                )
                self._datasets.append(dataset)
                self._current_dataset = None

            elif name == "sc:datasetLabel":
                self._current_dataset.label = self._last_char_data

            elif name == "sc:datasetURI":
                self._current_dataset.dataset_uri = self._last_char_data

            elif name == "sc:linkedDataPrefix":
                if self._current_prefix:
                    prefix = SitemapSemanticWebLinkedDataPrefix(
                        namespace=self._current_prefix.namespace,
                        prefix_value=self._current_prefix.prefix_value,
                        slice_method=self._current_prefix.slice_method_name,
                    )
                    self._current_dataset.linked_data_prefixes.append(prefix)
                    self._current_prefix = None

            elif self._current_prefix:
                if name == "sc:namespace":
                    self._current_prefix.namespace = self._last_char_data
                elif name == "sc:prefix":
                    self._current_prefix.prefix_value = self._last_char_data

            elif name == "sc:sparqlEndpointLocation":
                if self._current_endpoint:
                    endpoint = SitemapSemanticWebSparqlEndpoint(
                        location=self._current_endpoint.location,
                        graph_name=self._current_endpoint.graph_name,
                        slice_method=self._current_endpoint.slice_method_name,
                    )
                    self._current_dataset.sparql_endpoint = endpoint
                    self._current_endpoint = None

            elif self._current_endpoint:
                if name == "sc:endpointURI":
                    self._current_endpoint.location = self._last_char_data
                elif name == "sc:sparqlGraphName":
                    self._current_endpoint.graph_name = self._last_char_data

            elif name == "sc:dataDumpLocation":
                if self._last_char_data:
                    self._current_dataset.data_dump_locations.append(self._last_char_data)

            elif name == "sc:sampleURI":
                if self._last_char_data:
                    self._current_dataset.sample_uris.append(self._last_char_data)

            elif name == "lastmod":
                self._current_dataset.last_modified = self._last_char_data

            elif name == "changefreq":
                self._current_dataset.change_frequency = self._last_char_data

        super().xml_element_end(name=name)

    def xml_char_data(self, data: str) -> None:
        super().xml_char_data(data=data)

    def sitemap(self) -> AbstractSitemap:
        return SemanticWebSitemap(url=self._url, datasets=self._datasets)
