from odoo import api, fields, models


class MrpCampaignBillingWizard(models.TransientModel):
    _name = "mrp.campaign.billing.wizard"
    _inherit = "mrp.campaign.creator"
    _description = "Campaign wizard for production billing"

    _source_model = "sale.order.line"

    company_id = fields.Many2one(
        "res.company",
        related="campaign_id.company_id",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        campaign_id = self.env.context.get("default_campaign_id")
        if campaign_id and "product_id" in fields_list:
            campaign = self.env["mrp.campaign"].browse(campaign_id)
            if campaign.exists():
                res["product_id"] = campaign.product_id.id
                res["campaign_id"] = campaign.id
        return res

    def _get_available_lines(self, product_id) -> list[dict]:
        if not product_id:
            return []

        result = []
        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", product_id)]
        )

        for end_product in end_products:
            bom = end_product.bom_ids[:1]
            if not bom or not bom.billing_product_id:
                continue
            billing_product = bom.billing_product_id
            sols = self.env["sale.order.line"].search(
                [
                    ("product_id", "=", billing_product.id),
                    ("order_id.invoice_status", "!=", "invoiced"),
                ]
            )
            for sol in sols:
                allocated = sum(
                    self.env["mrp.campaign.demand.billing_proxy"]
                    .search([("sale_order_line_id", "=", sol.id)])
                    .mapped("promised_qty")
                )
                remaining = sol.product_uom_qty - allocated
                if remaining <= 0:
                    continue

                result.append(
                    {
                        "id": sol.id,
                        "name": f"{sol.order_id.name} | "
                        f"{sol.order_id.client_order_ref or ''}",
                        "qty": remaining,
                        "date": sol.order_id.date_order.isoformat()
                        if sol.order_id.date_order
                        else None,
                        "additional_ref": end_product.display_name,
                    }
                )

        return result

    def _get_valid_sources(self):
        if not self.product_id:
            return self.env["sale.order.line"]

        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", self.product_id.id)]
        )
        billing_products = end_products.mapped("bom_ids.billing_product_id")
        return self.env["sale.order.line"].search(
            [
                ("product_id", "in", billing_products.ids),
                ("order_id.invoice_status", "!=", "invoiced"),
            ]
        )

    def _create_demands(self, campaign) -> None:
        selected = self._get_selected_sources()
        if not selected:
            return

        grouped = {}
        for sol in selected:
            end_product = self._get_end_product_for_sol(sol)
            if not end_product:
                continue
            key = (end_product, sol)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(sol)

        for (end_product, sol), sols in grouped.items():
            bom = end_product.bom_ids[:1]
            target_qty = sum(s.product_uom_qty for s in sols)

            demand = self.env["mrp.campaign.demand"].create(
                {
                    "campaign_id": campaign.id,
                    "product_id": end_product.id,
                    "bom_id": bom.id if bom else False,
                    "target_qty": target_qty,
                    "sale_order_line_id": sol.id,
                }
            )

            proxy_values = [
                {
                    "demand_id": demand.id,
                    "sale_order_line_id": s.id,
                    "promised_qty": s.product_uom_qty,
                }
                for s in sols
            ]
            self.env["mrp.campaign.demand.billing_proxy"].create(proxy_values)

    def _get_end_product_for_sol(self, sol):
        if not self.product_id:
            return False

        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", self.product_id.id)]
        )
        for ep in end_products:
            bom = ep.bom_ids[:1]
            if bom and bom.billing_product_id.id == sol.product_id.id:
                return ep
        return False

    def process_wizard(self) -> dict | None:
        self.ensure_one()

        campaign = self.campaign_id
        result = None
        if not campaign:
            campaign = self.env["mrp.campaign"].create(
                {
                    "product_id": self.product_id.id,
                    "workflow_type": "production_billing",
                    "date_planned_start": self.planned_date,
                }
            )
            result = {
                "type": "ir.actions.act_window",
                "res_model": "mrp.campaign",
                "views": [[False, "form"]],
                "res_id": campaign.id,
                "target": "current",
            }

        self._create_demands(campaign)
        return result
