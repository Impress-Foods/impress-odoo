import json
import logging
from typing import NamedTuple

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from ..models.mrp_campaign import MrpCampaign
from ..models.mrp_campaign_demand import MrpCampaignDemand

_logger = logging.getLogger(__name__)


class Quantities(NamedTuple):
    bulk: float
    final: float


class CampaignBackorderWizard(models.TransientModel):
    _name = "mrp.campaign.backorder.wizard"
    _description = "Wizard to handle campaign backorder"

    campaign_id = fields.Many2one("mrp.campaign")
    allocation_json = fields.Text(string="Allocation Data")

    def action_backorder_campaign(self):
        self.ensure_one()
        self.action_confirm()
        return {"type": "ir.actions.act_window_close"}

    @api.model
    def make_allocation_json(self, campaign: MrpCampaign):
        values = {}
        values["available_bulk"] = sum(
            campaign.line_ids.filtered_domain(
                [("product_id", "=", campaign.product_id.id)]
            ).mapped("qty")
        )
        values["allocated_bulk"] = 0
        values["demands"] = [
            {
                "id": demand.id,
                "product": (demand.product_id.id, demand.product_id.display_name),
                "qty": demand.target_qty,  # Use target_qty here
                "planned_qty": demand.target_qty,  # Use target_qty as initial planned
                "total_allocated": demand.target_qty,  # Set initially to target_qty
                "needed_qty": 0,
                "factor": demand._get_anchor_factor(),
                "moves": [
                    {
                        "id": move.id,
                        "origin": move.origin,
                        "allocated_qty": 0,
                        "qty": move.product_uom_qty,
                    }
                    for move in demand.move_dest_ids
                ],
            }
            for demand in campaign.demand_line_ids
        ]

        return json.dumps(values)

    @api.model
    def default_get(self, fields_list) -> dict:
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign: MrpCampaign = self.env["mrp.campaign"].browse(active_id)
            res["campaign_id"] = campaign.id
            res["allocation_json"] = self.make_allocation_json(campaign)
        return res

    def action_confirm(self):
        self.ensure_one()
        data = json.loads(self.allocation_json)
        current_campaign = self.campaign_id
        backorder_campaign = self.env["mrp.campaign"]

        for demand_data in data["demands"]:
            demand_line: MrpCampaignDemand = self.env["mrp.campaign.demand"].browse(
                demand_data["id"]
            )
            original_target_qty: float = demand_line.target_qty
            factor: float = demand_data["factor"]
            keep_qty: float = demand_data["total_allocated"] / factor
            _logger.warning(f"orignal {original_target_qty} - keep {keep_qty}")
            comparison = float_compare(original_target_qty, keep_qty, 2)

            # Do nothing with fulfilled demands, error out on over fulfilled demands
            # and continue on under fulfilled demands
            match comparison:
                case 0:
                    continue
                case -1:
                    raise ValidationError(_("Allocated bulk qty > original target qty"))
                case _:
                    pass

            # For ease of use, round qty in units to ints
            if demand_line.product_id.uom_id.category_id == self.env.ref(
                "uom.product_uom_categ_unit"
            ):
                keep_qty = round(keep_qty)

            qty_to_bo = original_target_qty - keep_qty
            demand_line.target_qty -= qty_to_bo

            if not backorder_campaign:
                backorder_campaign = current_campaign.copy(
                    {"bo_source": current_campaign.id}
                )

            self.env["mrp.campaign.demand"].create(
                [
                    {
                        "product_id": demand_line.product_id.id,
                        "move_dest_ids": demand_line.move_dest_ids.ids,
                        "bom_id": demand_line.bom_id.id,
                        "campaign_id": backorder_campaign.id,
                    }
                ]
            ).write({"target_qty": qty_to_bo})

        return {"type": "ir.actions.act_window_close"}
