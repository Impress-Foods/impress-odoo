import logging

import requests
from pydantic import BaseModel
from werkzeug.urls import url_join

from odoo.orm.environments import Environment

from .schema import DominoLabel, DominoPrinter

_logger = logging.getLogger(__name__)


class DominoAPI:
    def __init__(self, env: Environment):
        self.url = (
            env["ir.config_parameter"].sudo().get_param("domino_printing.api_endpoint")
        )
        self.api_key = (
            env["ir.config_parameter"].sudo().get_param("domino_printing.api_key")
        )
        self.session = requests.Session()

    def __del__(self):
        self.session.close()

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

    def get_labels(self) -> list[DominoLabel]:
        response = self._make_api_request("/labels", method="GET")
        if response.status_code != 200:
            return []
        try:
            return [DominoLabel.model_validate(label) for label in response.json()]
        except Exception:
            return []

    def get_printers(self) -> list[DominoPrinter]:
        response = self._make_api_request("/printers", method="GET")
        if response.status_code != 200:
            return []
        try:
            return [DominoPrinter.model_validate(p) for p in response.json()]
        except Exception:
            return []

    def send_print_job(self, printer: int, label: str, data: dict) -> None:
        url = f"printers/{printer}/print/{label}"
        _logger.debug(data)
        self._make_api_request(url, "POST", data)
