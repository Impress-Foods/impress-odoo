import logging
from typing import Any

import psycopg2
import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class PrintServer(models.Model):
    _name = "print.server"
    _description = "Print server for label printing"

    active = fields.Boolean(default=True)
    name = fields.Char()
    url = fields.Char()
    api_key = fields.Char()
    timeout = fields.Integer()

    debug_logging = fields.Boolean(default=False)

    print_report_ids = fields.One2many("print.report", "print_server_id")

    def toggle_debug(self):
        for record in self:
            record.debug_logging = not record.debug_logging

    def _send(self, data) -> tuple[bool, Any]:
        self.ensure_one()
        headers = {"Authorization": "Bearer " + (self.api_key or "")}

        try:
            self.log_xml(f"{self.url} POST \n {data}", "print.report._send")
            r = requests.post(
                self.url, json=data, headers=headers, timeout=self.timeout or 30
            )
        except requests.ConnectionError as error:
            self.log_xml(
                f"Connection Error: {error} with the given URL: {self.url}",
                f"{self.name}",
            )
            return False, "Cannot reach the server. Please try again later."

        success = r.status_code == requests.codes.ok

        try:
            message = r.json()
        except ValueError:
            message = r.text

        return success, message

    def log_xml(self, xml_string, func):
        self.ensure_one()

        if self.debug_logging:
            self.env.flush_all()
            db_name = self.env.cr.dbname

            # Use a new cursor to avoid rollback that could be caused by an upper method
            try:
                db_registry = Registry(db_name)
                with db_registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    IrLogging = env["ir.logging"]
                    IrLogging.sudo().create(
                        {
                            "name": "print.server",
                            "type": "server",
                            "dbname": db_name,
                            "level": "DEBUG",
                            "message": xml_string,
                            "path": self.name,
                            "func": func,
                            "line": 1,
                        }
                    )
            except psycopg2.Error as e:
                _logger.warning(e)
