from odoo import api, fields, models


class MrpCampaignDemand(models.Model):
    _inherit = "mrp.campaign.demand"

    billing_proxy_ids = fields.One2many(
        "mrp.campaign.demand.billing_proxy",
        "demand_id",
    )

    billing_sale_order_ids = fields.Many2many(
        "sale.order",
        relation="mrp_campaign_demand_billing_sale_order_rel",
        compute="_compute_billing_sale_order_ids",
        store=True,
    )

    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Billing SOL",
        compute="_compute_sale_order_line_id",
        store=True,
    )

    @api.depends("billing_proxy_ids.sale_order_line_id")
    def _compute_sale_order_line_id(self):
        for rec in self:
            rec.sale_order_line_id = rec.billing_proxy_ids[:1].sale_order_line_id

    @api.depends("billing_proxy_ids", "billing_proxy_ids.sale_order_id")
    def _compute_billing_sale_order_ids(self):
        for rec in self:
            rec.billing_sale_order_ids = rec.billing_proxy_ids.mapped("sale_order_id")

    def unlink(self):
        self.billing_proxy_ids.unlink()
        return super().unlink()

    def create_campaign_line(self):
        res = super().create_campaign_line()
        for rec in self:
            if rec.sale_order_line_id and rec.campaign_line_id:
                rec.campaign_line_id.sale_order_line_id = rec.sale_order_line_id
        return res


class MrpCampaignDemandBillingProxy(models.Model):
    _name = "mrp.campaign.demand.billing_proxy"
    _description = "Proxy between mrp.campaign.demand and billing sale orders"

    demand_id = fields.Many2one(
        "mrp.campaign.demand",
        required=True,
        ondelete="cascade",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Billing Sale Order",
        related="sale_order_line_id.order_id",
        store=True,
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Billing Sale Order Line",
        required=True,
        ondelete="cascade",
    )
    promised_qty = fields.Float()
    campaign_id = fields.Many2one(related="demand_id.campaign_id", store=True)

    def _get_partition_wizard_fields(self) -> dict:
        self.ensure_one()
        so = self.sale_order_id
        sol = self.sale_order_line_id
        return {
            "proxy_id": self.id,
            "sale_order_id": so.id,
            "sale_order_name": so.name,
            "partner_id": so.partner_id.id,
            "customer": so.partner_id.name,
            "client_order_ref": so.client_order_ref,
            "fulfilled_qty": sol.qty_delivered if sol else 0,
            "target_qty": self.promised_qty,
            "state": so.state,
        }

    def _sync_target_qty(self) -> None:
        for proxy in self:
            proxy.demand_id.target_qty = sum(
                proxy.demand_id.billing_proxy_ids.mapped("promised_qty")
            )
