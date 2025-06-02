import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def action_open_label_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "label_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_product_id": self.product_id.id,
                "default_product_quantity": self.product_uom_qty,
            },
        }
