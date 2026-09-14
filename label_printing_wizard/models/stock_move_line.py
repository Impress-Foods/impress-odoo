from typing import Any

from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def action_open_label_wizard(self) -> dict:
        action: dict[str, str | list[Any] | dict[str, Any]] = {
            "type": "ir.actions.act_window",
            "res_model": "label_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_product_id": self.product_id.id,
                "default_product_uom_qty": self.quantity_product_uom,
            },
        }
        if self.lot_id:
            context: dict[str, Any] = action["context"]
            context["default_lot_id"] = self.lot_id.id
            context["default_model"] = "lot"

        return action
