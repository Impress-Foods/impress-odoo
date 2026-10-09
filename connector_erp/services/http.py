import logging
from urllib.parse import urljoin

import requests
from requests import RequestException

from odoo.addons.connector.exception import NetworkRetryableError

_logger = logging.getLogger(__name__)

# HTTP statuses that are worth retrying: rate limiting, timeouts and
# server-side errors. Any other 4xx is a permanent client error.
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_TIMEOUT = 30


class HTTPClient:
    """Minimal JSON-capable HTTP client for an ERP backend.

    Transient failures are raised as ``NetworkRetryableError`` so the job
    queue retries them with its configured backoff. Permanent failures keep
    the original ``requests`` exception so the job fails immediately.
    """

    def __init__(self, backend):
        self.backend = backend

    def request(
        self,
        path,
        method="GET",
        headers=None,
        params=None,
        data=None,
        timeout=DEFAULT_TIMEOUT,
    ):
        path = path.lstrip("/")
        url = urljoin(self.backend.base_url or "", path)

        request_headers = {"Authorization": f"Bearer {self.backend.api_key}"}
        if headers:
            request_headers.update(headers)

        try:
            response = requests.request(
                method,
                url,
                headers=request_headers,
                data=data,
                params=params,
                timeout=timeout,
            )
        except RequestException as err:
            raise NetworkRetryableError(f"HTTP request failed: {err}") from err

        if response.status_code in RETRYABLE_STATUS_CODES:
            raise NetworkRetryableError(
                f"HTTP {response.status_code} returned by {url}"
            )

        response.raise_for_status()
        return response
