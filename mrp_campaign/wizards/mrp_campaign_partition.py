import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpCampaignPartitionWizard(models.TransientModel):
    _name = "mrp.campaign.partition.wizard"
    _description = "Wizard to Partition an MRP Campaign (Split or Backorder)"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Original Campaign",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get("active_id"),
    )

    partition_mode = fields.Selection(
        [
            ("split", "Split into two new campaigns"),
            ("backorder", "Backorder remaining demand"),
        ],
        required=True,
        default="split",  # Default to split, as it's the most explicit action
    )

    # Fields for 'split' mode
    new_campaign_name_a = fields.Char(string="New Campaign Name 1")
    new_campaign_name_b = fields.Char(string="New Campaign Name 2")

    # Fields for 'backorder' mode (no explicit name needed, as it's generated)

    # This field will hold the JSON data for the custom widget
    partition_data_json = fields.Text(string="Demand Allocation Data")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign = self.env["mrp.campaign"].browse(active_id)
            res["campaign_id"] = campaign.id
            res["partition_data_json"] = self._make_partition_json(campaign)
            res["new_campaign_name_a"] = f"{campaign.name}-1"
            res["new_campaign_name_b"] = f"{campaign.name}-2"
        return res

    @api.model
    def _make_partition_json(self, campaign):
        """
        Prepares the JSON data structure for the custom allocation widget.
        It includes all demand lines and their current target_qty.
        """
        demands_data = []
        for demand in campaign.demand_line_ids:
            demands_data.append(
                {
                    "id": demand.id,
                    "product": (demand.product_id.id, demand.product_id.display_name),
                    "current_target_qty": demand.target_qty,  # The original quantity
                    "allocated_to_a": demand.target_qty,
                    "allocated_to_b": 0.0,  # Default: none to Campaign B / Backorder
                    "product_uom_name": demand.product_uom_id.name,
                    "moves": [
                        {
                            "id": move.id,
                            "origin": move.origin,
                            "qty": move.product_uom_qty,
                        }
                        for move in demand.move_dest_ids
                    ],
                }
            )

        return json.dumps({"demands": demands_data})

    def action_partition_campaign(self):
        self.ensure_one()
        data = json.loads(self.partition_data_json)
        original_campaign = self.campaign_id

        # Validate allocations
        for demand_data in data["demands"]:
            total_allocated = (
                demand_data["allocated_to_a"] + demand_data["allocated_to_b"]
            )
            if (
                abs(total_allocated - demand_data["current_target_qty"]) > 0.001
            ):  # Use float comparison
                raise UserError(
                    _(
                        "Total allocated quantity for product %s does "
                        "not match its original demand.",
                        demand_data["product"][1],
                    )
                )

        if self.partition_mode == "split":
            self._do_split(original_campaign, data["demands"])
        elif self.partition_mode == "backorder":
            self._do_backorder(original_campaign, data["demands"])

        return {"type": "ir.actions.act_window_close"}

    def _do_split(self, original_campaign, demands_data):
        """
        Performs the split operation: creates two
        new campaigns and cancels the original.
        """
        if not self.new_campaign_name_a or not self.new_campaign_name_b:
            raise UserError(_("New Campaign names are required for split mode."))

        new_campaign_a = original_campaign.copy(
            {
                "name": self.new_campaign_name_a,
                "line_ids": False,  # Clear demand lines to be recreated
                "bo_source": False,  # Not a backorder
            }
        )
        new_campaign_b = original_campaign.copy(
            {
                "name": self.new_campaign_name_b,
                "line_ids": False,  # Clear demand lines to be recreated
                "bo_source": False,  # Not a backorder
            }
        )

        for demand_data in demands_data:
            demand_line = self.env["mrp.campaign.demand"].browse(demand_data["id"])
            moves = demand_line.move_dest_ids

            if demand_data["allocated_to_a"] > 0:
                self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": new_campaign_a.id,
                        "product_id": demand_line.product_id.id,
                        "bom_id": demand_line.bom_id.id,
                        "move_dest_ids": [
                            (6, 0, moves.ids)
                        ],  # Link all moves for traceability
                        "target_qty": demand_data["allocated_to_a"],
                    }
                )
            if demand_data["allocated_to_b"] > 0:
                self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": new_campaign_b.id,
                        "product_id": demand_line.product_id.id,
                        "bom_id": demand_line.bom_id.id,
                        "move_dest_ids": [
                            (6, 0, moves.ids)
                        ],  # Link all moves for traceability
                        "target_qty": demand_data["allocated_to_b"],
                    }
                )

        # Cancel the original campaign to preserve history
        if original_campaign.state != "cancel":
            if original_campaign.production_ids:
                original_campaign.action_reset()
            original_campaign.state = "cancel"

        new_campaign_a._sync_date_planned_start()
        new_campaign_b._sync_date_planned_start()

    def _do_backorder(self, original_campaign, demands_data):
        """
        Performs the backorder operation: modifies original
        campaign and creates one new backorder campaign.
        """
        backorder_campaign = self.env["mrp.campaign"]  # Initialize empty

        for demand_data in demands_data:
            demand_line = self.env["mrp.campaign.demand"].browse(demand_data["id"])
            moves = demand_line.move_dest_ids

            # Update original demand line's target_qty
            demand_line.target_qty = demand_data[
                "allocated_to_a"
            ]  # 'A' is for original campaign

            # Create backorder demand line if there's quantity for backorder
            if demand_data["allocated_to_b"] > 0:
                if not backorder_campaign:
                    backorder_campaign = original_campaign.copy(
                        {
                            "name": f"{original_campaign.name}-BO",
                            "line_ids": False,  # Clear demand lines to be recreated
                            "bo_source": original_campaign.id,
                        }
                    )

                self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": backorder_campaign.id,
                        "product_id": demand_line.product_id.id,
                        "bom_id": demand_line.bom_id.id,
                        "move_dest_ids": [
                            (6, 0, moves.ids)
                        ],  # Link all moves for traceability
                        "target_qty": demand_data["allocated_to_b"],
                    }
                )

        if backorder_campaign:
            backorder_campaign._sync_date_planned_start()

        original_campaign._sync_date_planned_start()
