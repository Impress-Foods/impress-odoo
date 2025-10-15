from odoo import fields, models


class OrderPoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    vendor_code = fields.Char(related="supplier_id.product_code")
