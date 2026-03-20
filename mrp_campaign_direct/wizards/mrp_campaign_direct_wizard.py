import json

from odoo import api, fields, models


class MrpCampaignDirectWizard(models.TransientModel):
    _name = "mrp.campaign.direct.wizard"
    _inherit = "mrp.campaign.creator"
    _description = "Wizard for direct production campaigns"

    planned_date = fields.Date()

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.available_lines = json.dumps(self._get_available_lines(self.product_id.id))

    def _get_available_lines(self, product_id) -> list[dict]:
        if not product_id:
            return []

        moves = self.env["stock.move"].search(
            [
                ("product_id.anchor_product_id", "=", product_id),
                ("campaign_can_be_added", "=", True),
            ]
        )

        result = []
        for move in moves:
            result.append(
                {
                    "id": move.id,
                    "name": f"{move.origin or 'No origin'} "
                    f"| {move.product_id.display_name}",
                    "qty": move.campaign_qty_to_supply,
                    "date": move.date_deadline.isoformat()
                    if move.date_deadline
                    else None,
                    "additional_ref": move.sale_customer_ref or "",
                }
            )
        return result

    def _get_valid_sources(self):
        if not self.product_id:
            return self.env["stock.move"]

        return self.env["stock.move"].search(
            [
                ("product_id.anchor_product_id", "=", self.product_id.id),
                ("campaign_can_be_added", "=", True),
            ]
        )

    def _create_demands(self, campaign) -> None:
        selected_moves = self._get_selected_sources()
        if not selected_moves:
            return

        grouped = {}
        for move in selected_moves:
            product = move.product_id
            if product not in grouped:
                grouped[product] = []
            grouped[product].append(move)

        proxy_values = []
        for product, moves in grouped.items():
            bom = (
                self.env["mrp.bom"]
                ._bom_find(products=product, company_id=campaign.company_id.id)
                .get(product)
            )

            demand_line = campaign.demand_line_ids.filtered(
                lambda d, p=product: d.product_id == p
            )

            if not demand_line:
                demand_line = self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": campaign.id,
                        "product_id": product.id,
                        "bom_id": bom.id if bom else False,
                        "target_qty": sum(
                            move.campaign_qty_to_supply for move in moves
                        ),
                    }
                )
            else:
                demand_line.target_qty += sum(
                    move.campaign_qty_to_supply for move in moves
                )

            proxy_values += [
                {
                    "demand_id": demand_line.id,
                    "move_id": move.id,
                    "promised_qty": move.campaign_qty_to_supply,
                }
                for move in moves
            ]

        self.env["mrp.campaign.demand.proxy"].create(proxy_values)

    def process_wizard(self) -> dict | None:
        self.ensure_one()

        campaign = self.campaign_id
        result = None
        if not campaign:
            campaign = self.env["mrp.campaign"].create(
                {
                    "product_id": self.product_id.id,
                    "workflow_type": "direct",
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
