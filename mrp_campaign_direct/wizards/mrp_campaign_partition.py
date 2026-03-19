import json
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MrpCampaignPartitionWizardDirect(models.TransientModel):
    _name = "mrp.campaign.partition.wizard.direct"
    _description = "Wizard to Partition an MRP Campaign (Direct)"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
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
        default="split",
    )
    partition_data_json = fields.Text(string="Demand Allocation Data")

    # ----------------------------------------------------------------------
    # DEFAULTS
    # ----------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign = self.env["mrp.campaign"].browse(active_id)
            res["campaign_id"] = campaign.id
            res["partition_data_json"] = json.dumps(self._make_partition_json(campaign))
        return res

    # ----------------------------------------------------------------------
    # DATA BUILDING
    # ----------------------------------------------------------------------
    def _make_partition_json(self, campaign) -> dict:
        """Prepares the JSON data structure for the custom allocation widget."""
        campaign.ensure_one()
        root_line = campaign.line_ids.filtered(
            lambda line, campaign=campaign: line.product_id.id == campaign.product_id.id
        )
        if len(root_line) == 0:
            raise ValidationError(
                _("Cannot produce JSON for campaign without root line")
            )
        if len(root_line) > 1:
            raise ValidationError(
                _("Cannot produce JSON for campaign with multiple root lines")
            )

        return {
            "meta": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "mode": self.env.context.get("default_partition_mode", "split"),
            },
            "tree": self._build_tree_recursive(root_line[0]),
            "demand_moves": self._format_demand(campaign),
        }

    def _build_tree_recursive(self, line) -> dict[str, Any]:
        mos = line.production_ids
        planned = line.pre_buffer_qty
        done = sum(mos.mapped("qty_produced"))
        wip = line.committed_qty

        return {
            "line_id": line.id,
            "product_name": line.product_id.display_name,
            "product_id": line.product_id.id,
            "uom": line.product_id.uom_id.display_name,
            "quantities": {
                "planned": 0,
                "done": done,
                "wip": wip,
                "floor": wip,
                "initial_planned": planned,
            },
            "ratio": line._get_downstream_factor(),
            "upstream_branches": [
                self._build_tree_recursive(parent) for parent in line.upstream_line_ids
            ],
        }

    def _format_demand(self, campaign) -> list[dict[str, Any]]:
        """Aggregates demand from SOs/Deliveries linked to the campaign lines."""
        moves = []
        for demand in campaign.demand_line_ids:
            sorted_proxies = demand.demand_proxy_ids.sorted(
                key=lambda proxy: (
                    proxy.move_id.priority,
                    proxy.move_id.date_deadline or proxy.move_id.date,
                )
            )
            for proxy in sorted_proxies:
                moves.append(proxy._get_partition_wizard_fields())
        return moves

    # ----------------------------------------------------------------------
    # VALIDATION
    # ----------------------------------------------------------------------
    def _validate_json_demand(self, data: dict[str, Any]) -> dict[int, tuple]:
        demand_data = data.get("demand_moves")
        if demand_data is None:
            raise ValidationError(
                _("Malformed data: missing 'demand_moves' attribute in JSON.")
            )
        mapped_proxy = {v["proxy_id"]: v for v in demand_data}
        proxies = self.env["mrp.campaign.demand.proxy"].browse(mapped_proxy.keys())

        if set(mapped_proxy.keys()) != set(proxies.exists().ids):
            raise ValidationError(_("Not all proxies could be found in the database."))

        bad_proxies = [
            proxy for proxy in proxies if proxy.campaign_id != self.campaign_id
        ]
        if bad_proxies:
            raise ValidationError(
                _(
                    "Proxies %s are not associated with the current campaign",
                    bad_proxies,
                )
            )

        return {proxy.id: (proxy, mapped_proxy[proxy.id]) for proxy in proxies}

    # ----------------------------------------------------------------------
    # DELTAS
    # ----------------------------------------------------------------------
    def _get_deltas_demand(self, lines: dict[int, tuple]) -> dict[int, tuple]:
        deltas = {}
        for rec_id, (rec, intent) in lines.items():
            intended_qty = intent["fulfilled_qty"]

            if intended_qty < 0:
                raise ValidationError(
                    _(
                        "Trying to assign a negative quantity (%(qty)d) to a SO.",
                        qty=intended_qty,
                    )
                )
            if intended_qty > rec.upstream_qty:
                raise ValidationError(
                    _(
                        "Trying to assign a larger quantity "
                        "than required (%(assigned)d > %(demand)d).",
                        assigned=intended_qty,
                        demand=rec.upstream_qty,
                    )
                )

            delta = rec.promised_qty - intended_qty
            if delta != 0:
                deltas[rec_id] = (rec, delta)
        return deltas

    def _compute_demand_split_instructions(self, demand_deltas: dict) -> dict:
        instructions = {}
        for _proxy_id, (proxy, intent) in demand_deltas.items():
            demand = proxy.demand_id
            if demand.id not in instructions:
                instructions[demand.id] = {"qty": demand.target_qty, "bo_qty": 0.0}

            fulfilled_qty = intent.get("fulfilled_qty", proxy.promised_qty)
            delta = proxy.promised_qty - fulfilled_qty
            if delta > 0:
                instructions[demand.id]["qty"] -= delta
                instructions[demand.id]["bo_qty"] += delta
        return instructions

    # ----------------------------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------------------------
    def action_partition_campaign(self):
        self.ensure_one()
        data = json.loads(self.partition_data_json)
        demand_lines = self._validate_json_demand(data)
        demand_deltas = self._get_deltas_demand(demand_lines)
        demand_split_instructions = self._compute_demand_split_instructions(
            demand_deltas
        )

        self.campaign_id._split(demand_split_instructions)

        return {"type": "ir.actions.act_window_close"}
