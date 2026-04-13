import json
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class MrpCampaignPartition(models.TransientModel):
    _name = "mrp.campaign.wizard.partition"
    _description = "Base Wizard to Partition an MRP Campaign"

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
    workflow_type = fields.Selection([("direct", "Direct")])

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign = self.env["mrp.campaign"].browse(active_id)
            res["campaign_id"] = campaign.id
            res["partition_data_json"] = json.dumps(self._make_partition_json(campaign))
            res["workflow_type"] = campaign.workflow_type
        return res

    def _make_partition_json(self, campaign) -> dict:
        campaign.ensure_one()
        root_line = campaign.line_ids.filtered(
            lambda line, campaign=campaign: line.product_id.id == campaign.product_id.id
        )
        if len(root_line) == 0:
            raise ValidationError(
                self.env._("Cannot produce JSON for campaign without root line")
            )
        if len(root_line) > 1:
            raise ValidationError(
                self.env._("Cannot produce JSON for campaign with multiple root lines")
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

    def _format_demand(self, campaign) -> list[dict]:
        if campaign.workflow_type == "direct":
            moves = []
            for demand in campaign.demand_line_ids:
                targets = demand.target_ids.filtered_domain(
                    Domain("workflow_type", "=", "direct")
                )
                target_data = [(t, t._get_target()) for t in targets]
                target_data.sort(
                    key=lambda tm: (tm[1].priority, tm[1].date_deadline or tm[1].date)
                )
                for target, _move in target_data:
                    moves.append(target._get_partition_wizard_fields())
            return moves
        return []

    def _validate_json_production(self, data: dict[str, Any]) -> dict[int, tuple]:
        tree = data if "tree" not in data else data.get("tree")
        if tree is None:
            raise ValidationError(
                self.env._("Malformed data: missing 'tree' attribute in JSON.")
            )

        result = {}
        line_id = tree.get("line_id")
        if not line_id:
            raise ValidationError(
                self.env._("Malformed data: missing 'line_id' in tree.")
            )

        line = self.env["mrp.campaign.line"].browse(line_id)
        if not line.exists():
            raise ValidationError(
                self.env._(
                    "Could not find campaign line with id %(line)s", line=line_id
                )
            )
        if line.campaign_id != self.campaign_id:
            raise ValidationError(
                self.env._(
                    "Line %(line)s does not belong to campaign %(campaign)s",
                    line=line_id,
                    campaign=self.campaign_id.name,
                )
            )

        tree_data = {k: v for k, v in tree.items() if k != "upstream_branches"}
        result[line_id] = (line, tree_data)

        for branch in tree.get("upstream_branches", []):
            result.update(self._validate_json_production(branch))

        return result

    def _get_deltas_production(self, lines: dict[int, tuple]) -> dict[int, tuple]:
        deltas = {}
        for line_id, (line, intent) in lines.items():
            quantities = intent.get("quantities", {})
            planned = quantities.get("planned", 0)
            initial_planned = quantities.get("initial_planned", 0)
            floor = quantities.get("floor", 0)
            product_id = intent.get("product_id")

            if product_id and product_id != line.product_id.id:
                raise ValidationError(
                    self.env._(
                        "Product mismatch for line %(line_id)s: "
                        "expected %(expected)s, got %(actual)s",
                        line_id=line_id,
                        expected=line.product_id.display_name,
                        actual=self.env["product.product"]
                        .browse(product_id)
                        .display_name,
                    )
                )

            if planned < floor:
                raise ValidationError(
                    self.env._(
                        "Cannot plan less of %(product)s than the floor quantity. "
                        "Floor: %(floor)s, Planned: %(planned)s",
                        product=line.product_id.display_name,
                        floor=floor,
                        planned=planned,
                    )
                )

            if planned > initial_planned:
                raise ValidationError(
                    self.env._(
                        "Cannot plan more of %(product)s than the "
                        "initial planned quantity. "
                        "Initial: %(initial)s, Planned: %(planned)s",
                        product=line.product_id.display_name,
                        initial=initial_planned,
                        planned=planned,
                    )
                )

            delta = initial_planned - planned
            if delta != 0:
                deltas[line_id] = (line, delta)

        return deltas

    def _parse_demand_data(self, data: dict[str, Any]) -> dict[int, float]:
        """Parse and validate target quantities from wizard JSON.

        Validates:
        - JSON structure (demand_moves present)
        - Target records exist and belong to campaign
        - Quantity constraints (non-negative, not exceeding upstream_qty)

        Returns:
            Flat dict {target_id: final_promised_qty}
        """
        demand_data = data.get("demand_moves")
        if demand_data is None:
            raise ValidationError(
                self.env._("Malformed data: missing 'demand_moves' attribute in JSON.")
            )

        target_qtys = {}
        for item in demand_data:
            target_id = item.get("target_id")
            if not target_id:
                continue

            target = self.env["mrp.campaign.demand.target"].browse(target_id)
            if not target.exists():
                raise ValidationError(
                    self.env._("Target %s not found in database.", target_id)
                )
            if target.campaign_id != self.campaign_id:
                raise ValidationError(
                    self.env._("Target %s does not belong to this campaign.", target_id)
                )

            promised_qty = item.get("promised_qty", 0)
            if promised_qty < 0:
                raise ValidationError(
                    self.env._(
                        "Cannot assign negative quantity to target %s.", target_id
                    )
                )
            if promised_qty > target.upstream_qty:
                raise ValidationError(
                    self.env._(
                        "Quantity %(qty).2f exceeds upstream demand "
                        "%(max).2f for target %(id)s.",
                        qty=promised_qty,
                        max=target.upstream_qty,
                        id=target_id,
                    )
                )

            target_qtys[target_id] = promised_qty

        return target_qtys

    def action_partition_campaign(self):
        self.ensure_one()
        data = json.loads(self.partition_data_json or "{}")
        target_qtys = self._parse_demand_data(data)

        self.campaign_id._split(target_qtys)

        return {"type": "ir.actions.act_window_close"}
