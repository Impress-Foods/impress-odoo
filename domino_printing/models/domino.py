import logging
from urllib.parse import urljoin

import requests
from pydantic import BaseModel, ValidationError

from odoo.orm.environments import Environment

from .schema import DominoLabel, DominoPrinter

_logger = logging.getLogger(__name__)


class DominoAPI:
    def __init__(self, env: Environment):
        self.url = (
            env["ir.config_parameter"].sudo().get_param("domino_printing.api_endpoint")
        )
        if isinstance(self.url, str):
            self.url = self.url.rstrip("/") + "/"
        self.api_key = (
            env["ir.config_parameter"].sudo().get_param("domino_printing.api_key")
        )
        if not self.url or not self.api_key:
            raise ValueError(
                env._(
                    "Domino API endpoint and API key must be configured. "
                    "\n %(url)s \n %(key)s",
                    url=self.url,
                    key="*" * len(self.api_key or ""),
                )
            )
        self.session = requests.Session()

    def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: BaseModel | dict | None = None,
    ):
        access_url = urljoin(self.url, endpoint)
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}
        json_payload = None
        if payload:
            if isinstance(payload, dict):
                json_payload = payload
            else:
                json_payload = payload.model_dump(exclude_none=True)
        match method:
            case "GET":
                return self.session.get(access_url, headers=headers, timeout=30)
            case "POST":
                return self.session.post(
                    access_url,
                    headers=headers,
                    json=json_payload,
                    timeout=30,
                )
            case _:
                raise ValueError("Unsupported HTTP method: %s" % method)

    def get_labels(self) -> list[DominoLabel] | None:
        try:
            response = self._make_api_request("labels", method="GET")
        except requests.RequestException as error:
            _logger.warning("Failed to fetch labels from %s: %s", self.url, error)
            return None

        if response.status_code != 200:
            _logger.warning("Labels API returned %s", response.status_code)
            return None

        try:
            return [DominoLabel.model_validate(label) for label in response.json()]
        except (ValidationError, ValueError) as err:
            _logger.warning("Failed to parse labels response: %s", err)
            return None

    def get_printers(self) -> list[DominoPrinter] | None:
        try:
            response = self._make_api_request("printers", method="GET")
        except requests.RequestException as error:
            _logger.warning("Failed to fetch printers from %s: %s", self.url, error)
            return None

        if response.status_code != 200:
            _logger.warning("Printers API returned %s", response.status_code)
            return None

        try:
            return [DominoPrinter.model_validate(p) for p in response.json()]
        except (ValidationError, ValueError) as err:
            _logger.warning("Failed to parse printers response: %s", err)
            return None

    def send_print_job(self, printer: int, label: str, data: dict) -> bool:
        url = f"printers/{printer}/print/{label}"
        _logger.debug("Sending print job: printer=%s, label=%s", printer, label)
        try:
            response = self._make_api_request(url, "POST", data)
        except requests.RequestException as error:
            _logger.error(
                "Print job failed for printer %s, label %s: %s",
                printer,
                label,
                error,
            )
            return False

        if response.status_code not in (200, 201):
            _logger.error(
                "Print job failed for printer %s, label %s: %s",
                printer,
                label,
                response.text,
            )
            return False
        return True
