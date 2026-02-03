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
