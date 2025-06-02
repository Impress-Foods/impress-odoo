import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_open_label_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "label_wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_picking_id": self.id},
        }
