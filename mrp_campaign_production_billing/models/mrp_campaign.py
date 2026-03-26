from odoo import fields, models


class MrpCampaignProductionBilling(models.Model):
    _name = "mrp.campaign"
    _inherit = "mrp.campaign"

    workflow_type = fields.Selection(
        selection_add=[("production_billing", "Production Billing")]
    )

    def _recreate_targets(self, source_demand, new_demand, bo_qty) -> None:
        self.ensure_one()
        for target in source_demand.target_ids.filtered(
            lambda t: t.target_type == "billing"
        ):
            target.copy(
                {
                    "demand_id": new_demand.id,
                    "promised_qty": 0.0,
                    "fulfilled_qty": 0.0,
                }
            )
