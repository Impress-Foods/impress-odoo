import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

from ..services.http import HTTPClient

_logger = logging.getLogger(__name__)


class ERPBackend(models.Model):
    _name = "erp.backend"
    _description = "External Backend"

    name = fields.Char(required=True)
    backend_type = fields.Selection(selection=[], required=True)

    base_url = fields.Char(string="Base URL")
    api_key = fields.Char(string="API Key")

    last_sync_date = fields.Datetime(readonly=True, copy=False)

    company_id = fields.Many2one("res.company")

    partner_category_id = fields.Many2one(comodel_name="res.partner.category")

    def action_ping(self):
        self.ensure_one()
        self._ping_backend()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Success"),
                "message": self.env._(
                    "Backend at %(url)s is reachable.", url=self.base_url
                ),
                "type": "success",  # Options: 'success', 'danger', 'warning', 'info'
                "sticky": False,  # True makes it stay until dismissed
            },
        }

    def _ping_backend(self):
        self.ensure_one()
        self._request(path="/", method="GET")

    def _request(
        self,
        path: str,
        method: str = "GET",
        data: dict | None = None,
        params: dict | None = None,
    ):
        self.ensure_one()
        return HTTPClient(self).request(path, method=method, data=data, params=params)

    def _request_get(self, path: str, params: dict | None = None):
        return self._request(path, method="GET", params=params)

    def action_sync_partners(self):
        self.ensure_one()
        self._sync_partners()

    def _sync_partners(self):
        self.ensure_one()

        method = getattr(self, f"_sync_partners_{self.backend_type}", None)
        if not method:
            raise ValidationError(
                self.env._(
                    "Sync partners method not implemented for backend type %(type)s",
                    type=self.backend_type,
                )
            )

        res = method()
        success = "success" if res else "danger"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Success"),
                "message": self.env._("Contacts synced"),
                "type": success,  # Options: 'success', 'danger', 'warning', 'info'
                "sticky": False,  # True makes it stay until dismissed
            },
        }
