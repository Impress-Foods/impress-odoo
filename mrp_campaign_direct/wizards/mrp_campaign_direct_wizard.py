from odoo import api, fields, models
from odoo.fields import Command


class MrpCampaignDirectWizardLine(models.TransientModel):
    _name = "mrp.campaign.direct.wizard.line"
    _description = "Direct wizard selection line"
    _order = "product_id, id"

    wizard_id = fields.Many2one(
        "mrp.campaign.direct.wizard",
        required=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="move_id.product_id",
    )
    promised_qty = fields.Float(
        string="Quantity",
        related="move_id.campaign_qty_to_supply",
    )
    origin = fields.Char(
        string="Origin",
        related="move_id.origin",
    )
    date_deadline = fields.Datetime(
        string="Deadline",
        related="move_id.date_deadline",
    )
    state = fields.Selection(
        string="State",
        related="move_id.state",
    )
    customer_ref = fields.Char(
        string="Customer Ref",
        related="move_id.sale_customer_ref",
    )
    selected = fields.Boolean(default=True)


class MrpCampaignDirectWizard(models.TransientModel):
    _name = "mrp.campaign.direct.wizard"
    _inherit = "mrp.campaign.creator"

    _description = "Wizard for direct production campaigns"

    planned_date = fields.Date()

    selection_line_ids = fields.One2many(
        "mrp.campaign.direct.wizard.line",
        "wizard_id",
        string="Stock Moves",
        compute="_compute_selection_line_ids",
        readonly=False,
    )

    @api.depends("product_id")
    def _compute_selection_line_ids(self) -> None:
        for rec in self:
            existing = {}
            for line in rec.selection_line_ids:
                existing[line.move_id.id] = line.selected

            anchor_product = rec.product_id or rec.campaign_id.product_id
            if not anchor_product:
                rec.selection_line_ids = [(5, 0, 0)]
                continue

            moves = self.env["stock.move"].search(
                [
                    ("product_id.anchor_product_id", "=", anchor_product.id),
                    ("campaign_can_be_added", "=", True),
                ]
            )

            rec.selection_line_ids.unlink()
            values = [
                Command.create(
                    {
                        "move_id": move.id,
                        "selected": existing.get(move.id, True),
                    }
                )
                for move in moves
            ]
            rec.selection_line_ids = values

    def _create_demands(self, campaign) -> None:
        selected_lines = self.selection_line_ids.filtered("selected")
        if not selected_lines:
            return

        grouped = {}
        for line in selected_lines:
            product = line.product_id
            if product not in grouped:
                grouped[product] = []
            grouped[product].append(line)

        proxy_values = []
        for product, lines in grouped.items():
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
                        "target_qty": sum(line.promised_qty for line in lines),
                    }
                )
            else:
                demand_line.target_qty += sum(line.promised_qty for line in lines)

            proxy_values += [
                {
                    "demand_id": demand_line.id,
                    "move_id": line.move_id.id,
                    "promised_qty": line.promised_qty,
                }
                for line in lines
            ]

        self.env["mrp.campaign.demand.proxy"].create(proxy_values)

    def process_wizard(self) -> dict | None:
        self.ensure_one()

        campaign = self.campaign_id
        if not campaign:
            campaign = self.env["mrp.campaign"].create(
                {
                    "product_id": self.product_id.id,
                    "workflow_type": "direct",
                    "date_planned_start": self.planned_date,
                }
            )
            self._create_demands(campaign)
            return {
                "type": "ir.actions.act_window",
                "res_model": "mrp.campaign",
                "views": [[False, "form"]],
                "res_id": campaign.id,
                "target": "current",
            }

        self._create_demands(campaign)
        return None
