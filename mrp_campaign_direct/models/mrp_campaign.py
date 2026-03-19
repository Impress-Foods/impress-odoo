from odoo import fields, models


class MrpCampaignDirect(models.Model):
    _name = "mrp.campaign"
    _inherit = "mrp.campaign"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
    demand_proxy_ids = fields.One2many("mrp.campaign.demand.proxy", "campaign_id")
    workflow_type = fields.Selection(selection_add=[("direct", "Direct")])

    # ----------------------------------------------------------------------
    # INTERFACE OVERRIDES
    # ----------------------------------------------------------------------
    def _has_demands_to_partition(self) -> bool:
        return bool(self.demand_line_ids.mapped("demand_proxy_ids"))

    def _get_add_demand_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "direct":
            return "mrp.campaign.add.demand.direct"
        return super()._get_add_demand_wizard_model()

    def _get_partition_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "direct":
            return "mrp.campaign.partition.wizard.direct"
        return super()._get_partition_wizard_model()

    # ----------------------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------------------
    def _after_split(self, backorder_campaign) -> None:
        self.ensure_one()
        if self.workflow_type == "direct":
            for demand in self.demand_line_ids:
                demand._sync_proxy_target_qty()

            for demand in backorder_campaign.demand_line_ids:
                demand._sync_proxy_target_qty()
        return super()._after_split(backorder_campaign)
