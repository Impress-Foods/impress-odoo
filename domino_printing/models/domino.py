import logging

import requests
from pydantic import BaseModel
from werkzeug.urls import url_join

from .schema import DominoLabel, DominoPrinter

_logger = logging.getLogger(__name__)


class DominoAPI:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self.session = requests.Session()

    def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: BaseModel | dict | None = None,
    ):
        access_url = url_join(self.url, endpoint)
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}
        json_payload = None
        if payload:
            if isinstance(payload, dict):
                json_payload = payload
            else:
                json_payload = payload.model_dump(exclude_none=True)
        try:
            match method:
                case "GET":
                    response = self.session.get(access_url, headers=headers, timeout=30)
                case "POST":
                    response = self.session.post(
                        access_url,
                        headers=headers,
                        json=json_payload,
                        timeout=30,
                    )
        except requests.exceptions.ConnectionError as error:
            _logger.warning(
                f"Connection Error: {error} with the given URL: {access_url}"
            )
            return type("Response", (), {"status_code": 500, "text": str(error)})()
        return response

    def get_labels(self):
        response = self._make_api_request("/labels", method="GET")
        if response.status_code != 200:
            return []

        json = response.json()
        labels = [DominoLabel.model_validate(label) for label in json]

        return labels

    def get_printers(self):
        response = self._make_api_request("/printers", method="GET")
        if response.status_code != 200:
            return []
        try:
            printers = [DominoPrinter.model_validate(p) for p in response.json()]
        except Exception:
            return []
        return printers

    def send_print_job(self, printer: int, label: str, data: dict):
        url = f"printers/{printer}/print/{label}"
        _logger.debug(data)
        self._make_api_request(url, "POST", data)
