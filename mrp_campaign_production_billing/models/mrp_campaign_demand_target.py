from odoo import api, models


class MrpCampaignDemandTarget(models.Model):
    _inherit = "mrp.campaign.demand.target"

    @api.depends("workflow_type")
    def _compute_target_model(self) -> None:
        res = super()._compute_target_model()
        self.filtered_domain(
            [("workflow_type", "=", "production_billing")]
        ).target_model = "sale.order.line"
        return res

    @api.depends("workflow_type", "target_id")
    def _compute_upstream_qty(self) -> None:
        res = super()._compute_upstream_qty()
        for rec in self.filtered_domain([("workflow_type", "=", "production_billing")]):
            rec.upstream_qty = rec._get_target().product_uom_qty
        return res

    def _get_partition_wizard_fields(self) -> dict:
        self.ensure_one()
        res = super()._get_partition_wizard_fields()
        if self.workflow_type == "production_billing":
            sol = self._get_target()
            so = sol.order_id
            res.update(
                {
                    "customer": so.partner_id.name,
                    "customer_ref": so.client_order_ref,
                }
            )
        return res
