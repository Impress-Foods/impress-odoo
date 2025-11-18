from odoo import fields, models


class BOMLine(models.Model):
    _inherit = "mrp.bom.line"

    product_category_id = fields.Many2one(
        "product.category", related="product_id.categ_id"
    )
    vendor_code = fields.Char(related="product_id.vendor_code")
