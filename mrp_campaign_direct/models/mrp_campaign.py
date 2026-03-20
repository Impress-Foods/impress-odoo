from odoo import api, fields, models


class MrpCampaignDirect(models.Model):
    _name = "mrp.campaign"
    _inherit = "mrp.campaign"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
    demand_proxy_ids = fields.One2many("mrp.campaign.demand.proxy", "campaign_id")
    workflow_type = fields.Selection(selection_add=[("direct", "Direct")])

    # ----------------------------------------------------------------------
    # SALE ORDER LINKING
    # ----------------------------------------------------------------------
    sale_order_ids = fields.Many2many(
        "sale.order", compute="_compute_sale_order_ids", store=True
    )
    sale_order_count = fields.Integer(compute="_compute_sale_order_count")

    # ----------------------------------------------------------------------
    # INTERFACE OVERRIDES
    # ----------------------------------------------------------------------
    def _has_demands_to_partition(self) -> bool:
        return bool(self.demand_line_ids.mapped("demand_proxy_ids"))

    def _get_demand_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "direct":
            return "mrp.campaign.direct.wizard"
        return super()._get_demand_wizard_model()

    def _get_partition_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "direct":
            return "mrp.campaign.partition.wizard.direct"
        return super()._get_partition_wizard_model()

    # ----------------------------------------------------------------------
    # SALE ORDER COMPUTES & ACTIONS
    # ----------------------------------------------------------------------
    @api.depends("sale_order_ids")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = len(rec.sale_order_ids)

    @api.depends("demand_line_ids", "demand_line_ids.sale_order_ids")
    def _compute_sale_order_ids(self):
        for rec in self:
            rec.sale_order_ids = rec.demand_line_ids.mapped("sale_order_ids")

    def action_view_sos(self):
        self.ensure_one()
        if self.sale_order_count == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "views": [[False, "form"]],
                "res_id": self.sale_order_ids[0].id,
                "target": "current",
            }
        else:
            return {
                "type": "ir.actions.act_window",
                "name": "Sale orders for %s" % self.name,
                "res_model": "sale.order",
                "domain": [("id", "in", self.sale_order_ids.ids)],
                "view_mode": "tree,form",
                "target": "current",
            }

    # ----------------------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------------------
    def _after_split(self, backorder_campaign) -> None:
        self.ensure_one()
        if self.workflow_type == "direct":
            for demand in self.demand_line_ids:
                demand.demand_proxy_ids._sync_target_qty()

            for demand in backorder_campaign.demand_line_ids:
                demand.demand_proxy_ids._sync_target_qty()
        return super()._after_split(backorder_campaign)
