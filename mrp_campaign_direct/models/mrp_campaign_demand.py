from odoo import api, fields, models


class MrpCampaignDemand(models.Model):
    _inherit = "mrp.campaign.demand"

    demand_proxy_ids = fields.One2many(
        "mrp.campaign.demand.proxy",
        "demand_id",
    )

    sale_order_ids = fields.Many2many(
        "sale.order", compute="_compute_sale_order_ids", store=True
    )

    @api.depends("demand_proxy_ids", "demand_proxy_ids.sale_order_id")
    def _compute_sale_order_ids(self):
        for rec in self:
            rec.sale_order_ids = rec.demand_proxy_ids.mapped("sale_order_id")

    def unlink(self):
        self.demand_proxy_ids.unlink()
        return super().unlink()


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
    sale_order_id = fields.Many2one(related="move_id.sale_line_id.order_id")

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
        values = {
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

        group_id = move.group_id
        if group_id and group_id.sale_id:
            values["customer_ref"] = group_id.sale_id.client_order_ref

        return values

    def _sync_target_qty(self) -> None:
        """Recompute target_qty on parent demand based on all proxies."""
        for proxy in self:
            proxy.demand_id.target_qty = sum(
                proxy.demand_id.demand_proxy_ids.mapped("promised_qty")
            )
