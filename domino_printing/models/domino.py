import logging

import requests
from pydantic import BaseModel
from werkzeug.urls import url_join

_logger = logging.getLogger(__name__)


class DominoAPI:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self.session = requests.Session()

    def _make_api_request(
        self, endpoint: str, method: str = "GET", payload: BaseModel | None = None
    ) -> dict:
        access_url = url_join(self.url, endpoint)
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}
        try:
            match method:
                case "GET":
                    self.session.get(access_url, headers=headers, timeout=30)
        except requests.exceptions.ConnectionError as error:
            _logger.warning(
                f"Connection Error: {error} with the given URL: {access_url}"
            )
            return {
                "errors": {
                    "timeout": "Cannot reach the server. Please try again later."
                }
            }
        return {}
