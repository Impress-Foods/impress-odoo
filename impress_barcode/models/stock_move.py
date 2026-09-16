from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_fields_stock_barcode(self) -> list[str]:
        fields = super()._get_fields_stock_barcode()
        fields.extend(["description_picking", "location_dest_id"])
        return fields
