"""Implementation of :mod:`usp.web_client.abstract_client` with Requests."""

import logging
from http import HTTPStatus

import requests  # type: ignore[import-untyped]

from usp import __version__

from .abstract_client import (
    RETRYABLE_HTTP_STATUS_CODES,
    AbstractWebClient,
    AbstractWebClientResponse,
    AbstractWebClientSuccessResponse,
    RequestWaiter,
    WebClientErrorResponse,
)

log = logging.getLogger(__name__)


class RequestsWebClientSuccessResponse(AbstractWebClientSuccessResponse):
    """
    requests-based successful response.
    """

    __slots__ = [
        "__requests_response",
        "__max_response_data_length",
    ]

    def __init__(
        self,
        requests_response: requests.Response,
        max_response_data_length: int | None = None,
    ):
        """
        :param requests_response: Response data
        :param max_response_data_length: Maximum data length, or ``None`` to not restrict.
        """
        self.__requests_response = requests_response
        self.__max_response_data_length = max_response_data_length

    def status_code(self) -> int:
        return int(self.__requests_response.status_code)

    def status_message(self) -> str:
        return self.__requests_response.reason or HTTPStatus(self.status_code()).phrase

    def header(self, case_insensitive_name: str) -> str | None:
        return self.__requests_response.headers.get(case_insensitive_name.lower(), None)

    def raw_data(self) -> bytes:
        return (
            self.__requests_response.content[: self.__max_response_data_length]
            if self.__max_response_data_length
            else self.__requests_response.content
        )

    def url(self) -> str:
        return self.__requests_response.url


class RequestsWebClientErrorResponse(WebClientErrorResponse):
    """
    Error response from the Requests parser.
    """

    pass


class RequestsWebClient(AbstractWebClient):
    """requests-based web client to be used by the sitemap fetcher."""

    __USER_AGENT = f"ultimate_sitemap_parser/{__version__}"

    __HTTP_REQUEST_TIMEOUT: tuple[float, float] = (9.05, 60.0)
    """
    HTTP request timeout.

    Some webservers might be generating huge sitemaps on the fly, so this is why it's rather big.
    """

    __slots__ = [
        "__max_response_data_length",
        "__timeout",
        "__proxies",
        "__verify",
        "__waiter",
        "__session",
    ]

    def __init__(
        self,
        verify=True,
        wait: float | None = None,
        random_wait: bool = False,
        session: requests.Session | None = None,
    ):
        """
        :param verify: whether certificates should be verified for HTTPS requests.
        :param wait: time to wait between requests, in seconds.
        :param random_wait: if true, wait time is multiplied by a random number between 0.5 and 1.5.
        :param session: a custom session object to use, or None to create a new one.
        """
        self.__max_response_data_length: int | None = None
        self.__timeout: float | tuple[float, float] | None = self.__HTTP_REQUEST_TIMEOUT
        self.__proxies: dict[str, str] = {}
        self.__verify: bool = verify
        self.__waiter: RequestWaiter = RequestWaiter(wait, random_wait)
        self.__session: requests.Session = session or requests.Session()

    def set_timeout(self, timeout: float | tuple[float, float] | None) -> None:
        """Set HTTP request timeout.

        See also: `Requests timeout docs <https://requests.readthedocs.io/en/latest/user/advanced/#timeouts>`__

        :param timeout: An integer to use as both the connect and read timeouts,
            or a tuple to specify them individually, or None for no timeout
        """
        # Used mostly for testing
        self.__timeout = timeout

    def set_proxies(self, proxies: dict[str, str]) -> None:
        """
        Set a proxy for the request.

        :param proxies: Proxy definition where the keys are schemes ("http" or "https") and values are the proxy address.
            Example: ``{'http': 'http://user:pass@10.10.1.10:3128/'}, or an empty dict to disable proxy.``
        """
        # Used mostly for testing
        self.__proxies = proxies

    def set_max_response_data_length(
        self, max_response_data_length: int | None
    ) -> None:
        self.__max_response_data_length = max_response_data_length

    def get(self, url: str) -> AbstractWebClientResponse:
        self.__waiter.wait()
        try:
            response = self.__session.get(
                url,
                timeout=self.__timeout,
                stream=True,
                headers={"User-Agent": self.__USER_AGENT},
                proxies=self.__proxies,
                verify=self.__verify,
            )
        except requests.exceptions.Timeout as ex:
            # Retryable timeouts
            return RequestsWebClientErrorResponse(message=str(ex), retryable=True)

        except requests.exceptions.RequestException as ex:
            # Other errors, e.g. redirect loops
            return RequestsWebClientErrorResponse(message=str(ex), retryable=False)

        else:
            if 200 <= response.status_code < 300:
                return RequestsWebClientSuccessResponse(
                    requests_response=response,
                    max_response_data_length=self.__max_response_data_length,
                )
            message = f"{response.status_code} {response.reason}"
            log.debug(f"Response content: {response.text}")

            return (
                RequestsWebClientErrorResponse(message=message, retryable=True)
                if response.status_code in RETRYABLE_HTTP_STATUS_CODES
                else RequestsWebClientErrorResponse(
                    message=message, retryable=False
                )
            )
