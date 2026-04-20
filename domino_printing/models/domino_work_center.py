from odoo import api, fields, models
from odoo.exceptions import UserError

from .domino import DominoAPI


class DominoProductionLineModel(models.Model):
    _name = "domino.work.center"
    _description = "Domino Printer"

    name = fields.Char(required=True)
    printer_id = fields.Integer(required=True, string="Printer ID")
    label_ids = fields.Many2many("domino.label")
    workcenter_ids = fields.Many2many("mrp.workcenter")
    active = fields.Boolean(default=True)

    @api.model
    def _cron_sync_printers(self):
        self._sync_printers()

    def _sync_printers(self):
        dom = DominoAPI(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("domino_printing.api_endpoint"),
            self.env["ir.config_parameter"].sudo().get_param("domino_printing.api_key"),
        )

        try:
            printers = dom.get_printers()
            existing = {rec.printer_id: rec for rec in self.search([])}

            for printer in printers:
                if printer.id in existing:
                    existing[printer.id].write(
                        {
                            "name": printer.name,
                            "active": printer.active,
                        }
                    )
                else:
                    self.create(
                        {
                            "name": printer.name,
                            "printer_id": printer.id,
                            "active": printer.active,
                        }
                    )
        except Exception as e:
            raise UserError(self.env._("Failed to sync printers: %(e)s", e)) from e

    def action_sync_work_centers(self):
        self._sync_printers()
