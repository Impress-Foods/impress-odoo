from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command, Domain

from .domino import DominoAPI


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

        try:
            labels = dom.get_labels()
            existing = {rec.domino_id: rec for rec in self.search(Domain.TRUE)}
            for label in labels:
                if label.id in existing:
                    printers = self.env["domino.printer"].search(
                        Domain("printer_id", "in", label.printer_ids)
                    )

                    existing[label.id].write(
                        {
                            "domino_id": label.id,
                            "schema_json": label.buffer_schema.model_dump_json(),
                            "printer_ids": [Command.set(printers.ids)],
                        }
                    )
                else:
                    printers = self.env["domino.printer"].search(
                        Domain("printer_id", "in", label.printer_ids)
                    )
                    self.create(
                        {
                            "name": label.name,
                            "domino_id": label.id,
                            "schema_json": label.buffer_schema.model_dump_json(),
                            "printer_ids": [Command.set(printers.ids)],
                        }
                    )
        except Exception as e:
            raise UserError(
                self.env._("Failed to sync labels: %(error)s", error=e)
            ) from e

    def action_sync_labels(self):
        self._sync_labels()
