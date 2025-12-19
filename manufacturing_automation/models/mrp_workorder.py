from odoo import fields, models


class MrpWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    associated_campaign_id = fields.Many2one(
        related="production_id.associated_campaign_id"
    )
    campaign_color = fields.Char(related="production_id.campaign_color")
