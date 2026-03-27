from odoo import fields, models


class MrpCampaignCreator(models.Model):
    _inherit = "mrp.campaign.wizard.creator"

    workflow_type = fields.Selection(
        selection_add=[("production_billing", "Production Billing")]
    )

    def _get_available_lines(self) -> list[dict]:
        self.ensure_one()
        if self.workflow_type != "production_billing":
            return super()._get_available_lines()

        if not self.product_id:
            return []

        result = []
        seen_sol_ids: set[int] = set()
        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", self.product_id.id)]
        )

        for end_product in end_products:
            bom = self.env["mrp.bom"]._bom_find(end_product).get(end_product)
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
                if sol.id in seen_sol_ids:
                    continue
                seen_sol_ids.add(sol.id)

                allocated = sum(
                    self.env["mrp.campaign.demand.target"]
                    .sudo()
                    .search(
                        [
                            ("workflow_type", "=", "production_billing"),
                            ("target_id", "=", sol.id),
                        ]
                    )
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
        if self.workflow_type != "production_billing":
            return super()._get_valid_sources()

        if not self.product_id:
            return self.env["sale.order.line"]

        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", self.product_id.id)]
        )
        billing_products = self.env["product.product"]
        for ep in end_products:
            bom = self.env["mrp.bom"]._bom_find(ep).get(ep)
            if bom and bom.billing_product_id:
                billing_products |= bom.billing_product_id
        return self.env["sale.order.line"].search(
            [
                ("product_id", "in", billing_products.ids),
                ("order_id.invoice_status", "!=", "invoiced"),
            ]
        )

    def _create_demands(self, campaign) -> None:
        if self.workflow_type != "production_billing":
            return super()._create_demands(campaign)
        return self._create_demands_production_billing(campaign)

    def _create_demands_production_billing(self, campaign) -> None:
        selected = self._get_selected_sources()
        if not selected:
            return

        grouped = {}
        for sol in selected:
            end_product = self._get_end_product_for_sol(sol)
            if not end_product:
                continue
            key = (end_product, sol.order_id.id)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(sol)

        for (end_product, _order_id), sols in grouped.items():
            sol = sols[0]
            bom = self.env["mrp.bom"]._bom_find(end_product).get(end_product)

            demand = campaign.demand_line_ids.filtered(
                lambda d, ep=end_product, so_id=sol.order_id.id: (
                    d.product_id == ep and d.sale_order_line_id.order_id.id == so_id
                )
            )
            if not demand:
                demand = self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": campaign.id,
                        "product_id": end_product.id,
                        "bom_id": bom.id if bom else False,
                        "sale_order_line_id": sol.id,
                    }
                )
                target_values = [
                    {
                        "demand_id": demand.id,
                        "workflow_type": "production_billing",
                        "target_id": s.id,
                        "promised_qty": s.product_uom_qty,
                    }
                    for s in sols
                ]
                self.env["mrp.campaign.demand.target"].create(target_values)
            else:
                existing_target_sol_ids = set(demand.target_ids.mapped("target_id").ids)
                new_sols = sols.filtered(
                    lambda s, existing=existing_target_sol_ids: s.id not in existing
                )
                if new_sols:
                    target_values = [
                        {
                            "demand_id": demand.id,
                            "workflow_type": "production_billing",
                            "target_id": s.id,
                            "promised_qty": s.product_uom_qty,
                        }
                        for s in new_sols
                    ]
                    self.env["mrp.campaign.demand.target"].create(target_values)

    def _get_end_product_for_sol(self, sol):
        if not self.product_id:
            return False

        end_products = self.env["product.product"].search(
            [("anchor_product_id", "=", self.product_id.id)]
        )
        for ep in end_products:
            bom = self.env["mrp.bom"]._bom_find(ep).get(ep)
            if bom and bom.billing_product_id.id == sol.product_id.id:
                return ep
        return False
