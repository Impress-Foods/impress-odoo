import logging
from urllib.parse import urljoin

import requests
from requests import RequestException

_logger = logging.getLogger(__name__)


class HTTPClient:
    def __init__(self, backend):
        self.backend = backend

    def request(
        self,
        path: str,
        method: str = "GET",
        headers: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
    ):
        path = path.lstrip("/")
        url = urljoin(self.backend.base_url, path)

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
                timeout=30,
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            raise RequestException(f"HTTP request failed: {e}") from e
