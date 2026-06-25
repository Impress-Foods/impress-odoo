import logging

from odoo import api, fields, models
from odoo.fields import Command

from .domino import DominoAPI

_logger = logging.getLogger(__name__)


class DominoLabelModel(models.Model):
    _name = "domino.label"
    _description = "Domino Label"

    name = fields.Char(required=True)
    domino_id = fields.Integer()
    active = fields.Boolean(default=True)
    printer_ids = fields.Many2many("domino.printer")
    schema_json = fields.Text(
        string="Buffer Schema",
        help="JSON schema for the label buffer fields",
    )

    @api.model
    def _cron_sync_labels(self):
        self._sync_labels()

    def _sync_labels(self):
        dom = DominoAPI(self.env)
        labels = dom.get_labels()
        if labels is None:
            _logger.warning("Failed to fetch labels from Domino API — skipping sync")
            return

        existing = {rec.domino_id: rec for rec in self.search([])}
        synced_ids = set()
        for label in labels:
            printers = self.env["domino.printer"].search(
                [("printer_id", "in", label.printer_ids)]
            )
            synced_ids.add(label.id)
            if label.id in existing:
                existing[label.id].write(
                    {
                        "domino_id": label.id,
                        "schema_json": label.buffer_schema.model_dump_json(),
                        "printer_ids": [Command.set(printers.ids)],
                    }
                )
            else:
                self.create(
                    {
                        "name": label.name,
                        "domino_id": label.id,
                        "schema_json": label.buffer_schema.model_dump_json(),
                        "printer_ids": [Command.set(printers.ids)],
                    }
                )

        if synced_ids:
            stale = self.search([("domino_id", "not in", list(synced_ids))])
            if stale:
                stale.unlink()

    def action_sync_labels(self):
        self._sync_labels()
