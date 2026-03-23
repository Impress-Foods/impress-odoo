from odoo import api, fields, models


class MrpCampaignDemand(models.Model):
    _inherit = "mrp.campaign.demand"

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

    @api.depends("target_ids", "campaign_id.workflow_type")
    def _compute_sale_order_line_id(self):
        for rec in self:
            if rec.campaign_id.workflow_type != "production_billing":
                rec.sale_order_line_id = False
                continue
            billing_targets = rec.target_ids.filtered(
                lambda t: t.target_type == "billing"
            )
            first_target = billing_targets[:1]
            rec.sale_order_line_id = first_target.source_ref if first_target else False

    @api.depends("target_ids", "campaign_id.workflow_type")
    def _compute_billing_sale_order_ids(self):
        for rec in self:
            if rec.campaign_id.workflow_type != "production_billing":
                rec.billing_sale_order_ids = False
                continue
            sale_orders = self.env["sale.order"]
            for target in rec.target_ids.filtered(lambda t: t.target_type == "billing"):
                if target.source_ref and target.source_ref._name == "sale.order.line":
                    sale_orders |= target.source_ref.order_id
            rec.billing_sale_order_ids = sale_orders

    def create_campaign_line(self):
        res = super().create_campaign_line()
        for rec in self:
            if rec.sale_order_line_id and rec.campaign_line_id:
                rec.campaign_line_id.sale_order_line_id = rec.sale_order_line_id
        return res

    def unlink(self):
        self.target_ids.unlink()
        return super().unlink()
