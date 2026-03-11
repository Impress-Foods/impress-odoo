from odoo import api, fields, models


class MrpCampaignDemand(models.Model):
    _inherit = "mrp.campaign.demand"

    sale_order_ids = fields.Many2many(
        "sale.order", compute="_compute_sale_order_ids", store=True
    )

    @api.depends("demand_proxy_ids", "demand_proxy_ids.sale_order_id")
    def _compute_sale_order_ids(self):
        for rec in self:
            rec.sale_order_ids = rec.demand_proxy_ids.mapped("sale_order_id")


class MrpCampaignDemandProxy(models.Model):
    _inherit = "mrp.campaign.demand.proxy"

    sale_order_id = fields.Many2one(related="move_id.sale_line_id.order_id")

    def _get_partition_wizard_fields(self):
        self.ensure_one()
        values = super()._get_partition_wizard_fields()

        group_id = self.move_id.group_id
        if group_id:
            if self.move_id.group_id.sale_id:
                order_ref = group_id.sale_id.client_order_ref
                values["customer_ref"] = order_ref
        return values
