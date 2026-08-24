from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    net_weight = fields.Float()
