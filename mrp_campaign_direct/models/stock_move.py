from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
    campaign_proxy_ids = fields.One2many("mrp.campaign.demand.proxy", "move_id")
    campaign_qty_to_supply = fields.Float(
        compute="_compute_campaign_qty_to_supply", store=True
    )
    campaign_can_be_added = fields.Boolean(
        compute="_compute_campaign_can_be_added", store=True
    )
    sale_customer_ref = fields.Char(
        string="Customer Reference", related="sale_line_id.order_id.client_order_ref"
    )

    # ----------------------------------------------------------------------
    # COMPUTES
    # ----------------------------------------------------------------------
    @api.depends(
        "campaign_proxy_ids", "campaign_proxy_ids.promised_qty", "product_uom_qty"
    )
    def _compute_campaign_qty_to_supply(self) -> None:
        for rec in self:
            qty_fulfilled = sum(rec.campaign_proxy_ids.mapped("promised_qty"))
            rec.campaign_qty_to_supply = max(rec.product_uom_qty - qty_fulfilled, 0)

    @api.depends("campaign_qty_to_supply", "state")
    def _compute_campaign_can_be_added(self) -> None:
        for rec in self:
            value = (rec.campaign_qty_to_supply > 0) and (
                rec.state not in ["cancel", "done", "draft"] and (not rec.move_dest_ids)
            )
            rec.campaign_can_be_added = value
