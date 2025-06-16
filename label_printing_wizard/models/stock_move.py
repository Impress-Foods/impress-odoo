import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def action_open_label_wizard(self) -> dict:
        if len(self.move_line_ids) == 1:
            # If there is only 1 move line, we can treat the move as a move line
            return self.move_line_ids[0].action_open_label_wizard()

        action = {
            "type": "ir.actions.act_window",
            "res_model": "label.wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_product_id": self.product_id.id,
                "default_product_quantity": self.product_uom_qty,
            },
        }

        return action
