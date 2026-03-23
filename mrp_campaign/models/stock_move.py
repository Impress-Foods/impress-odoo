from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_customer_ref = fields.Char(
        string="Customer Reference", related="sale_line_id.order_id.client_order_ref"
    )

    def _get_qty_to_fulfill(self) -> float:
        self.ensure_one()
        targets = self.env["mrp.campaign.demand.target"].search(
            [("target_model", "=", "stock.move"), ("target_id", "=", self.id)]
        )

        promised_qty = sum(targets.mapped("promised_qty"))
        return self.product_uom_qty - promised_qty
