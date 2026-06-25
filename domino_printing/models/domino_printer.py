import logging

from odoo import api, fields, models

from .domino import DominoAPI

_logger = logging.getLogger(__name__)


class DominoPrinterModel(models.Model):
    _name = "domino.printer"
    _description = "Domino Printer"

    name = fields.Char(required=True)
    printer_id = fields.Integer(required=True, string="Printer ID")
    label_ids = fields.Many2many("domino.label")
    active = fields.Boolean(default=True)

    @api.model
    def _cron_sync_printers(self):
        self._sync_printers()

    def _sync_printers(self):
        dom = DominoAPI(self.env)
        printers = dom.get_printers()
        if printers is None:
            _logger.warning("Failed to fetch printers from Domino API — skipping sync")
            return

        existing = {rec.printer_id: rec for rec in self.search([])}
        synced_ids = set()
        for printer in printers:
            synced_ids.add(printer.id)
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

        if synced_ids:
            stale = self.search([("printer_id", "not in", list(synced_ids))])
            if stale:
                stale.unlink()

    def action_sync_printers(self):
        self._sync_printers()
