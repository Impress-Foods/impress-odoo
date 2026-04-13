from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MrpCampaignDemand(models.Model):
    _inherit = "mrp.campaign.demand"

    billing_sale_order_id = fields.Many2one(related="sale_order_line_id.order_id")

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

            sol_id = list(set(rec.target_ids.mapped("target_id")))
            if len(sol_id) > 1:
                raise ValidationError(
                    self.env._("Multiple Sale Order Line for a single demand")
                )
            if len(sol_id) == 0:
                rec.sale_order_line_id = False
            rec.sale_order_line_id = rec.env["sale.order.line"].browse(sol_id)

    def create_campaign_line(self):
        res = super().create_campaign_line()
        for rec in self:
            if rec.sale_order_line_id and rec.campaign_line_id:
                rec.campaign_line_id.sale_order_line_id = rec.sale_order_line_id
        return res
