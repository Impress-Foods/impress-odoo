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

    It is deliberately split into small seams so a concrete ERP can adapt the
    transport without rewriting it:

    * ``_build_url`` builds the absolute URL from the backend's ``base_url``
      and a path.
    * ``_auth_headers`` returns the authentication headers; the default uses a
      bearer token built from ``api_key``.
    * ``_default_headers`` merges the transport-wide headers with the
      authentication headers.
    * ``request`` performs an authenticated call, ``request_unauthenticated``
      performs a call without authentication.
    * ``_transport`` is the single place that talks to ``requests`` and
      classifies failures.

    Transient failures are raised as ``NetworkRetryableError`` so the job
    queue retries them with its configured backoff. Permanent failures keep
    the original ``requests`` exception so the job fails immediately.
    """

    DEFAULT_HEADERS = {"Accept": "application/json"}

    def __init__(self, backend):
        self.backend = backend

    def _build_url(self, path):
        base_url = self.backend.base_url or ""
        # urljoin would drop the last path segment of the base URL when it
        # does not end with a slash, so normalise it first.
        if base_url and not base_url.endswith("/"):
            base_url += "/"
        return urljoin(base_url, path.lstrip("/"))

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.backend.api_key}"}

    def _default_headers(self):
        headers = dict(self.DEFAULT_HEADERS)
        headers.update(self._auth_headers())
        return headers

    def request(
        self,
        path,
        method="GET",
        headers=None,
        params=None,
        data=None,
        json=None,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Perform an authenticated request and return the response."""
        return self._transport(
            method,
            self._build_url(path),
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
            authenticated=True,
        )

    def request_unauthenticated(
        self,
        path,
        method="POST",
        headers=None,
        params=None,
        data=None,
        json=None,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Perform a request without authentication headers.

        Used for calls that cannot carry a token yet, typically an OAuth2
        token request.
        """
        return self._transport(
            method,
            self._build_url(path),
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
            authenticated=False,
        )

    def _transport(
        self,
        method,
        url,
        headers=None,
        params=None,
        data=None,
        json=None,
        timeout=DEFAULT_TIMEOUT,
        authenticated=True,
    ):
        if authenticated:
            request_headers = self._default_headers()
        else:
            request_headers = dict(self.DEFAULT_HEADERS)
        if headers:
            request_headers.update(headers)

        try:
            response = requests.request(
                method,
                url,
                headers=request_headers,
                data=data,
                json=json,
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
