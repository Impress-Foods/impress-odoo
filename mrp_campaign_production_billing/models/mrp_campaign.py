from odoo import fields, models


class MrpCampaignProductionBilling(models.Model):
    _name = "mrp.campaign"
    _inherit = "mrp.campaign"

    workflow_type = fields.Selection(
        selection_add=[("production_billing", "Production Billing")]
    )

    def _get_demand_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "production_billing":
            return "mrp.campaign.billing.wizard"
        return super()._get_add_demand_wizard_model()

    def _get_partition_wizard_model(self) -> str:
        self.ensure_one()
        if self.workflow_type == "production_billing":
            return "mrp.campaign.partition.wizard.production_billing"
        return super()._get_partition_wizard_model()
