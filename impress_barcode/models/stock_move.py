import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.extend(
            [
                "lot_ids",
                "quantity",
                "product_qty",
                "product_uom_qty",
                "bom_line_id",
                "description_picking",
                "product_uom",
            ]
        )
        return res
