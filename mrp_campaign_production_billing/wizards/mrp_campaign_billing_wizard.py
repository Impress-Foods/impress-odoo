import logging

from odoo import api, fields, models
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class MrpCampaignBillingWizardLine(models.TransientModel):
    _name = "mrp.campaign.billing.wizard.line"
    _description = "Billing wizard selection line"
    _order = "sale_order_line_id, id"

    wizard_id = fields.Many2one(
        "mrp.campaign.billing.wizard",
        required=True,
        ondelete="cascade",
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="SO Line",
        required=True,
        ondelete="cascade",
    )
    end_product_id = fields.Many2one(
        "product.product",
        string="End Product",
        required=True,
        ondelete="cascade",
    )
    billing_product_id = fields.Many2one(
        "product.product",
        string="Billing Product",
        required=True,
        ondelete="cascade",
    )
    promised_qty = fields.Float(string="Quantity")
    selected = fields.Boolean(default=True)
    sale_order_id = fields.Many2one(related="sale_order_line_id.order_id")
    client_order_ref = fields.Char(related="sale_order_id.client_order_ref")

    def _make_values(self) -> list[dict]:
        return [
            {
                "sale_order_line_id": line.sale_order_line_id.id,
                "promised_qty": line.promised_qty,
            }
            for line in self.filtered("selected")
        ]


class MrpCampaignBillingWizard(models.TransientModel):
    _name = "mrp.campaign.billing.wizard"
    _inherit = "mrp.campaign.creator"

    company_id = fields.Many2one(
        "res.company",
        related="campaign_id.company_id",
    )

    selection_line_ids = fields.One2many(
        "mrp.campaign.billing.wizard.line",
        "wizard_id",
        string="Sale Order Lines",
        compute="_compute_selection_line_ids",
        readonly=False,
    )

    @api.model
    def default_get(self, fields_list) -> None:
        _logger.warning("Running default get")
        res = super().default_get(fields_list)

        if self.product_id:
            res["selection_line_ids"] = self._make_selection_lines()
        return res

    @api.depends("product_id")
    def _compute_selection_line_ids(self) -> None:
        for rec in self:
            existing = {}
            for line in rec.selection_line_ids:
                key = (line.end_product_id.id, line.sale_order_line_id.id)
                existing[key] = line.selected

            end_products = self.env["product.product"].search(
                [("anchor_product_id", "=", rec.product_id.id)]
            )

            rec.selection_line_ids.unlink()
            values = []
            for end_product in end_products:
                bom = end_product.bom_ids[:1]
                if not bom or not bom.billing_product_id:
                    continue
                billing_product = bom.billing_product_id
                sols = self.env["sale.order.line"].search(
                    [("product_id", "=", billing_product.id)]
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

                    key = (end_product.id, sol.id)
                    selected = existing.get(key, True)
                    values.append(
                        Command.create(
                            {
                                "end_product_id": end_product.id,
                                "billing_product_id": billing_product.id,
                                "sale_order_line_id": sol.id,
                                "promised_qty": remaining,
                                "selected": selected,
                                "wizard_id": rec.id,
                            }
                        )
                    )
            rec.selection_line_ids = values

    def _create_demands(self, campaign) -> None:
        selected_lines = self.selection_line_ids.filtered("selected")
        if not selected_lines:
            return

        grouped = {}
        for line in selected_lines:
            key = (line.end_product_id, line.sale_order_line_id)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(line)

        for (end_product, sol), lines in grouped.items():
            bom = end_product.bom_ids[:1]
            target_qty = sum(line.promised_qty for line in lines)

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
                    "sale_order_line_id": line.sale_order_line_id.id,
                    "promised_qty": line.promised_qty,
                }
                for line in lines
            ]
            self.env["mrp.campaign.demand.billing_proxy"].create(proxy_values)

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
