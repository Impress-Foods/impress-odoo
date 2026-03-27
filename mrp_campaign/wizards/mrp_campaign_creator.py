import json

from odoo import api, fields, models


class MrpCampaignCreator(models.Model):
    _name = "mrp.campaign.wizard.creator"
    _description = "Wizard for campaign creation"

    product_id = fields.Many2one(
        comodel_name="product.product",
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
    )
    planned_date = fields.Date(default=lambda self: fields.Date.today())
    campaign_id = fields.Many2one("mrp.campaign")

    workflow_type = fields.Selection([("direct", "Direct")])

    available_lines = fields.Char(
        help="JSON array of demand lines. Fields: id, name, qty, date, additional_ref",
    )
    selected_line_ids = fields.Char(
        help="JSON array of selected line IDs",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        if res.get("campaign_id"):
            res["product_id"] = (
                self.env["mrp.campaign"].browse(res["campaign_id"]).product_id.id
            )
        return res

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.ensure_one()
        self.available_lines = json.dumps(self._get_available_lines())
        self.selected_line_ids = "[]"

    def _get_available_lines(self) -> list[dict]:
        self.ensure_one()
        if self.workflow_type == "direct":
            result = []
            moves = self._get_valid_sources()
            for move in moves:
                result.append(
                    {
                        "id": move.id,
                        "name": f"{move.origin or 'No origin'} "
                        f"| {move.product_id.display_name}",
                        "qty": move._get_qty_to_fulfill(),
                        "date": move.date_deadline.isoformat()
                        if move.date_deadline
                        else None,
                        "additional_ref": move.sale_customer_ref or "",
                    }
                )
            return result
        return []

    def _get_valid_sources(self):
        self.ensure_one()
        if self.workflow_type == "direct":
            if not self.product_id:
                return self.env["stock.move"]
            return self.env["stock.move"].search(
                [
                    ("product_id.anchor_product_id", "=", self.product_id.id),
                    ("state", "not in", ["draft", "done", "cancelled"]),
                    ("picking_id.picking_type_code", "=", "outgoing"),
                ]
            )

        return []

    def _get_selected_sources(self):
        selected_ids = json.loads(self.selected_line_ids or "[]")
        valid_sources = self._get_valid_sources()
        if valid_sources:
            return valid_sources.filtered(lambda r: r.id in selected_ids)
        else:
            return []

    def _create_demands(self, campaign) -> None:
        if self.workflow_type == "direct":
            self._create_demands_direct(campaign)

    def _create_demands_direct(self, campaign) -> None:
        selected_moves = self._get_selected_sources()
        if not selected_moves:
            return

        grouped = {}
        for move in selected_moves:
            product = move.product_id
            if product not in grouped:
                grouped[product] = []
            grouped[product].append(move)

        target_values = []
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
                    }
                )

            for move in moves:
                target_values.append(
                    {
                        "demand_id": demand_line.id,
                        "workflow_type": "direct",
                        "target_id": move.id,
                        "promised_qty": move._get_qty_to_fulfill(),
                    }
                )

        self.env["mrp.campaign.demand.target"].create(target_values)

    def process_wizard(self) -> dict | None:
        campaign = self.campaign_id
        result = None
        if not campaign:
            campaign = self.env["mrp.campaign"].create(
                {
                    "product_id": self.product_id.id,
                    "workflow_type": self.workflow_type,
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
