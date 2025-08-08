import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def action_open_label_wizard(self) -> dict:
        action = {
            "type": "ir.actions.act_window",
            "res_model": "label_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_product_id": self.product_id.id,
                "default_product_quantity": self.quantity_product_uom,
            },
        }
        if self.lot_id:
            action["context"]["default_lot_id"] = self.lot_id.id  # type: ignore
            action["context"]["default_model"] = "lot"  # type: ignore
        return action
