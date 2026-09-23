import logging
from typing import Any
from urllib.parse import urlparse

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PrintingApiServer(models.Model):
    _name = "printing.api.server"
    _description = "HTTP API printing endpoint"
    _order = "name"

    name = fields.Char(required=True)
    url = fields.Char(required=True)
    method = fields.Selection(
        selection=[
            ("get", "GET"),
            ("post", "POST"),
            ("put", "PUT"),
            ("patch", "PATCH"),
        ],
        required=True,
        default="post",
    )
    api_key = fields.Char(
        copy=False,
        groups="base_report_to_printer.printing_group_manager",
    )
    timeout = fields.Integer(default=30)
    active = fields.Boolean(default=True)
    debug_logging = fields.Boolean(default=False)
    printer_ids = fields.One2many(
        comodel_name="printing.printer",
        inverse_name="api_server_id",
        string="Printers",
    )

    @api.constrains("url")
    def _check_url(self):
        for record in self:
            parsed_url = urlparse(record.url or "")
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValidationError(
                    self.env._(
                        "The API endpoint URL must be a valid HTTP or HTTPS URL."
                    )
                )

    @api.constrains("timeout")
    def _check_timeout(self):
        for record in self:
            if record.timeout and record.timeout <= 0:
                raise ValidationError(
                    self.env._("The API timeout must be greater than zero.")
                )

    def toggle_debug(self):
        for record in self:
            record.debug_logging = not record.debug_logging

    def _get_headers(self) -> dict[str, str]:
        self.ensure_one()
        headers = {"Accept": "application/json"}
        # The secret is manager-only in the UI/ORM, but the backend must be
        # able to use it when a regular print user submits a job.
        api_key = self.sudo().api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _get_response_message(response: requests.Response) -> Any:
        try:
            return response.json()
        except (AttributeError, ValueError):
            return getattr(response, "text", "")

    def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one flat API payload and return a transport result.

        The endpoint deliberately returns a result dictionary instead of
        raising for HTTP/network failures. This keeps the backend compatible
        with the report-to-printer contract and lets the dispatcher display a
        useful notification for both failures and successful submissions.
        """
        self.ensure_one()
        timeout = self.timeout or 30
        try:
            response = requests.request(
                self.method,
                self.url,
                json=payload,
                headers=self._get_headers(),
                timeout=timeout,
            )
        except (TypeError, ValueError) as error:
            _logger.warning("Could not serialize printing API payload: %s", error)
            return {
                "success": False,
                "message": self.env._("The print job contains invalid data."),
            }
        except requests.RequestException as error:
            _logger.warning("Could not reach printing API %s: %s", self.name, error)
            return {
                "success": False,
                "message": self.env._(
                    "Could not reach the printing API. Please try again."
                ),
            }

        status_code = response.status_code
        success = 200 <= status_code < 300
        message = self._get_response_message(response)
        if not success and not message:
            message = self.env._("HTTP status %(status)s", status=status_code)
        if self.debug_logging:
            _logger.debug(
                "Printing API %s returned HTTP %s for method %s",
                self.name,
                status_code,
                self.method,
            )
        return {
            "success": success,
            "message": message,
            "status_code": status_code,
        }
