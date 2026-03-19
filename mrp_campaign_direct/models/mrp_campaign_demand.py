from odoo import fields, models


class MrpCampaignDemandProxy(models.Model):
    _name = "mrp.campaign.demand.proxy"
    _description = "Proxy between mrp.campaign.demand and stock.move"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
    demand_id = fields.Many2one(
        "mrp.campaign.demand", required=True, ondelete="cascade"
    )
    move_id = fields.Many2one("stock.move", required=True, ondelete="cascade")
    promised_qty = fields.Float()
    campaign_id = fields.Many2one(related="demand_id.campaign_id", store=True)
    origin = fields.Char(related="move_id.origin")

    # ----------------------------------------------------------------------
    # COMPUTED FIELDS
    # ----------------------------------------------------------------------
    upstream_qty = fields.Float(
        related="move_id.product_uom_qty", string="Upstream Demand"
    )

    # ----------------------------------------------------------------------
    # METHODS
    # ----------------------------------------------------------------------
    def _get_partition_wizard_fields(self) -> dict:
        self.ensure_one()
        move = self.move_id
        return {
            "proxy_id": self.id,
            "move_id": move.id,
            "product_id": move.product_id.id,
            "product_name": move.product_id.display_name,
            "origin": move.origin or move.picking_id.name,
            "customer": move.partner_id.name or "Internal",
            "fulfilled_qty": 0,
            "target_qty": self.promised_qty,
            "uom": move.product_uom.display_name,
            "deadline": move.date_deadline.strftime("%Y-%m-%d")
            if move.date_deadline
            else False,
        }

    def _sync_target_qty(self) -> None:
        """Recompute target_qty on parent demand based on all proxies."""
        for proxy in self:
            proxy.demand_id.target_qty = sum(
                proxy.demand_id.demand_proxy_ids.mapped("promised_qty")
            )
