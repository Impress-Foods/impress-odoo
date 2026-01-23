from odoo import fields, models


class MrpWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    campaign_id = fields.Many2one(related="production_id.campaign_id")
    campaign_color = fields.Char(related="production_id.campaign_color")
    campaign_sequence = fields.Integer(
        string="Campaign Sequence",
        related="production_id.campaign_sequence",
        store=True,
        readonly=True,
        help="Sequence of the parent campaign",
    )
