from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    domino_name = fields.Char(
        string="Domino Product Name",
        help="Product name to send to Domino (used in field mappings)",
    )
