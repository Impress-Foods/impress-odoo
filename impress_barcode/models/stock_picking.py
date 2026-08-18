import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("origin")
        return res

    def _get_stock_barcode_data(self):
        data = super()._get_stock_barcode_data()
        moves = self.move_ids
        products = self.move_ids.product_id

        # Add all stock.move from picking to the cache
        data["records"]["stock.move"] = moves.read(
            moves._get_fields_stock_barcode(), load=False
        )

        # To allow for further overrides, do not overwrite the records sent to cache.
        # Instead, add the missing ones by taking all products in the stock.move and add
        # only add those not already present
        data["records"]["product.product"].extend(
            [
                i
                for i in products.read(products._get_fields_stock_barcode(), load=False)
                if i["id"] not in [j["id"] for j in data["records"]["product.product"]]
            ]
        )

        return data

    def action_open_picking_backend_form(self):
        self.ensure_one()
        view = self.env.ref("stock.view_picking_form")
        return {
            "name": self.env._("Open picking"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "views": [(view.id, "form")],
            "res_id": self.id,
        }
