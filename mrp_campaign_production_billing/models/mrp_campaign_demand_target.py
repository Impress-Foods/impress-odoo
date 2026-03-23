from odoo import models


class MrpCampaignDemandTarget(models.Model):
    _inherit = "mrp.campaign.demand.target"

    def _get_partition_wizard_fields(self):
        self.ensure_one()
        res = super()._get_partition_wizard_fields()
        if self.workflow_type == "billing":
            sol = self._get_target()
            so = sol.order_id
            res.update(
                {
                    "sale_order_id": so.id,
                    "sale_order_name": so.name,
                    "partner_id": so.partner_id.id,
                    "customer": so.partner_id.name,
                    "client_order_ref": so.client_order_ref,
                    "state": so.state,
                }
            )
        return res
