from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_campaign_manufactured = fields.Boolean()
    mrp_max_batch_size = fields.Integer()
