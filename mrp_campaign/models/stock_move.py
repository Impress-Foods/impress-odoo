import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    campaign_qty_to_supply = fields.Float(
        compute="_compute_campaign_qty_to_supply", store=True
    )
    campaign_proxy_ids = fields.One2many("mrp.campaign.demand.proxy", "move_id")

    campaign_can_be_added = fields.Boolean(
        compute="_compute_campaign_can_be_added", store=True
    )

    @api.depends(
        "campaign_proxy_ids", "campaign_proxy_ids.promised_qty", "product_uom_qty"
    )
    def _compute_campaign_qty_to_supply(self):
        for rec in self:
            qty_fulfilled = sum(rec.campaign_proxy_ids.mapped("promised_qty"))
            rec.campaign_qty_to_supply = rec.product_uom_qty - qty_fulfilled

    @api.depends("campaign_qty_to_supply", "state")
    def _compute_campaign_can_be_added(self):
        for rec in self:
            value = (rec.campaign_qty_to_supply > 0) and (
                rec.state not in ["cancel", "done", "draft"]
            )
            rec.campaign_can_be_added = value
