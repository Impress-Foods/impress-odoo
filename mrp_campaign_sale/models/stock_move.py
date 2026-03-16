from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"
    sale_customer_ref = fields.Char(
        string="Customer Reference", related="sale_line_id.order_id.client_order_ref"
    )
