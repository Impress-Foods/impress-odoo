import json
import logging
from typing import NamedTuple

from odoo import api, fields, models

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
                "qty": demand.qty,
                "planned_qty": 0,
                "total_allocated": 0,
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
        demands: dict[MrpCampaignDemand, Quantities] = {}
        for demand in data["demands"]:
            demand_line: MrpCampaignDemand = self.env["mrp.campaign.demand"].browse(
                demand["id"]
            )
            allocated = demand["total_allocated"]
            final_fulfilled = allocated / demand_line._get_anchor_factor()
            demands[demand_line] = Quantities(allocated, final_fulfilled)
        _logger.warning(demands)
