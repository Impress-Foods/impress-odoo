from odoo import fields, models


class MrpCampaignPartition(models.TransientModel):
    _inherit = "mrp.campaign.wizard.partition"

    workflow_type = fields.Selection(
        selection_add=[("production_billing", "Production Billing")]
    )

    def _format_demand(self, campaign) -> list[dict]:
        if campaign.workflow_type != "production_billing":
            return super()._format_demand(campaign)

        moves = []
        for demand in campaign.demand_line_ids:
            billing_targets = demand.target_ids.filtered(
                lambda t: t.workflow_type == "production_billing"
            )
            for target in billing_targets:
                moves.append(target._get_partition_wizard_fields())
        return moves
