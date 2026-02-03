from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Manufacturing Campaign",
        copy=False,
        index=True,
        help="The campaign this move is a part of.",
    )
    campaign_wizard_ids = fields.Many2many(
        "mrp.campaign.creator", relation="mrp_campaign_creator_actual"
    )
    campaign_valid_wizard_ids = fields.Many2many(
        "mrp.campaign.creator", relation="mrp_campaign_creator_valid"
    )
