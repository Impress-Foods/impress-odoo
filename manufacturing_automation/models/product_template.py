from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_campaign_manufactured = fields.Boolean()
    mrp_max_batch_size = fields.Integer()
    campaign_bucket_size = fields.Integer(string="Bucket Size", default=1)
    campaign_bucket_type = fields.Selection(
        selection=[("day", "Day"), ("week", "Week"), ("month", "Month")], default="day"
    )
