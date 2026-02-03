import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpCampaignSplitWizard(models.TransientModel):
    _name = "mrp.campaign.split.wizard"
    _description = "Wizard to Split a Manufacturing Campaign"

    original_campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Original Campaign",
        required=True,
        readonly=True,
    )

    line_ids = fields.One2many(
        "mrp.campaign.split.wizard.line",
        "wizard_id",
        string="Demand Move Assignments",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign = self.env["mrp.campaign"].browse(active_id)
            res["original_campaign_id"] = campaign.id

            moves = campaign.line_ids.mapped("move_dest_ids")
            lines_vals = [
                (
                    0,
                    0,
                    {
                        "move_id": move.id,
                        "destination_campaign": "A",
                    },
                )
                for move in moves
            ]
            res["line_ids"] = lines_vals
        return res

    def action_split_campaign(self):
        """
        Takes all the moves from the original campaign and redistributes them
        into two new campaigns based on the user's assignments in the wizard.
        """
        self.ensure_one()

        assigned_to_a = self.line_ids.filtered(
            lambda line: line.destination_campaign == "1"
        )
        assigned_to_b = self.line_ids.filtered(
            lambda line: line.destination_campaign == "2"
        )

        if not assigned_to_a or not assigned_to_b:
            raise UserError(
                _(
                    "To split a campaign, you must assign demands to both "
                    "'New Campaign 1' and 'New Campaign 2'."
                )
            )

        moves_a = assigned_to_a.mapped("move_id")
        self._create_new_campaign(moves_a, "1")

        moves_b = assigned_to_b.mapped("move_id")
        self._create_new_campaign(moves_b, "2")

        # Cancel the original campaign to preserve history
        if self.original_campaign_id.state != "cancel":
            if self.original_campaign_id.production_ids:
                self.original_campaign_id.action_reset()
            self.original_campaign_id.state = "cancel"

        return {"type": "ir.actions.act_window_close"}

    def _create_new_campaign(self, moves, suffix):
        """Helper method to create a new campaign from a set of moves."""
        original_campaign = self.original_campaign_id

        new_campaign = original_campaign.copy(
            {
                "name": f"{original_campaign.name}-{suffix}",
                "line_ids": False,
            }
        )

        boms_by_product = self.env["mrp.bom"]._bom_find(
            products=moves.mapped("product_id")
        )

        # Group moves by both product and its corresponding BoM to create lines
        grouped_lines_data = {}
        for move in moves:
            bom = boms_by_product.get(move.product_id, self.env["mrp.bom"])
            key = (move.product_id.id, bom.id)
            if key not in grouped_lines_data:
                grouped_lines_data[key] = self.env["stock.move"]
            grouped_lines_data[key] |= move

        for (product_id, bom_id), line_moves in grouped_lines_data.items():
            self.env["mrp.campaign.line"].create(
                {
                    "campaign_id": new_campaign.id,
                    "product_id": product_id,
                    "bom_id": bom_id,
                    "move_dest_ids": [(6, 0, line_moves.ids)],
                }
            )

        new_campaign._sync_date_planned_start()
        return new_campaign


class MrpCampaignSplitWizardLine(models.TransientModel):
    _name = "mrp.campaign.split.wizard.line"
    _description = "Line model for the Campaign Split Wizard"
    _order = "move_id"

    wizard_id = fields.Many2one(
        "mrp.campaign.split.wizard", required=True, ondelete="cascade"
    )
    move_id = fields.Many2one(
        "stock.move", string="Demand Move", readonly=True, required=True
    )
    product_id = fields.Many2one(related="move_id.product_id", readonly=True)
    product_uom_qty = fields.Float(related="move_id.product_uom_qty", readonly=True)
    date_deadline = fields.Datetime(related="move_id.date_deadline", readonly=True)

    destination_campaign = fields.Selection(
        [("1", "New Campaign 1"), ("2", "New Campaign 2")],
        string="Destination",
        default="1",
        required=True,
    )
