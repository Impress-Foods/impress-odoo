import logging
from contextlib import contextmanager

from odoo import fields, models

from ..services.http import HTTPClient

_logger = logging.getLogger(__name__)


class ErpBackend(models.AbstractModel):
    """Base for every ERP backend (the framework's "collection").

    A concrete backend is one model per ERP (e.g. ``erp.katana.backend``).
    It holds the connection settings and acts as the namespace the connector
    components subscribe to.
    """

    _name = "erp.backend"
    _inherit = ["connector.backend"]
    _description = "ERP Backend"

    name = fields.Char(required=True)
    base_url = fields.Char()
    api_key = fields.Char()
    last_sync_date = fields.Datetime(readonly=True, copy=False)
    company_id = fields.Many2one("res.company")

    def _make_client(self):
        """Return the low-level API client for this backend.

        Concrete backends override this to return their own client. The
        client is instantiated once per work session and shared by every
        component taking part in it.
        """
        self.ensure_one()
        return HTTPClient(self)

    @contextmanager
    def work_on(self, model_name, **kwargs):
        """Open a work session with the API client already injected."""
        self.ensure_one()
        kwargs.setdefault("erp_client", self._make_client())
        with super().work_on(model_name, **kwargs) as work:
            yield work

    def _request(self, path, method="GET", data=None, params=None):
        self.ensure_one()
        return self._make_client().request(
            path, method=method, data=data, params=params
        )

    def _request_get(self, path, params=None):
        return self._request(path, method="GET", params=params)

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
                "type": "success",
                "sticky": False,
            },
        }

    def _ping_backend(self):
        self.ensure_one()
        self._request(path="/", method="GET")

    def _run_batch_import(self, model_name, **kwargs):
        """Enqueue the import of every missing record of a binding model."""
        self.ensure_one()
        with self.work_on(model_name) as work:
            importer = work.component(usage="batch.importer")
            return importer.run(**kwargs)

    def _run_record_import(self, model_name, external_id, **kwargs):
        """Import a single external record synchronously."""
        self.ensure_one()
        with self.work_on(model_name) as work:
            importer = work.component(usage="record.importer")
            return importer.run(external_id, **kwargs)
