import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_open_label_wizard(self) -> dict:
        if len(self.move_ids) == 1:
            # If there is only 1 move, we can treat the picking as a single move
            return self.move_ids[0].action_open_label_wizard()

        return {
            "type": "ir.actions.act_window",
            "res_model": "label.wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_picking_id": self.id},
        }
