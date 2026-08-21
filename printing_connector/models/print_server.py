import logging

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PrintServer(models.Model):
    _name = "print.server"
    _description = "Print server for label printing"

    active = fields.Boolean(default=True)
    name = fields.Char()
    url = fields.Char()
    api_key = fields.Char()
    timeout = fields.Integer()

    print_report_ids = fields.One2many("print.report", "print_server_id")

    def _serialize(self, data):
        return data

    def _send(self, data):
        self.ensure_one()
        headers = {"Authorization": "Bearer " + (self.api_key or "")}
        r = requests.post(
            self.url, json=data, headers=headers, timeout=self.timeout or 30
        )

        result = {}

        if r.status_code != requests.codes.ok:
            result["success"] = False
            result["message"] = r.json()
        else:
            result["success"] = True
            result["message"] = "Label sent to printer."

        return result
