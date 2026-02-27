import json
import logging
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.mrp_campaign import MrpCampaign
from ..models.mrp_campaign_line import CampaignLine

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
        default="split",
    )

    partition_data_json = fields.Text(string="Demand Allocation Data")

    @api.model
    def default_get(self, fields_list):  # pragma: no coverage
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "mrp.campaign" and active_id:
            campaign = self.env["mrp.campaign"].browse(active_id)
            res["campaign_id"] = campaign.id
            res["partition_data_json"] = json.dumps(self._make_partition_json(campaign))
        return res

    @api.model
    def _make_partition_json(self, campaign: MrpCampaign) -> dict:
        """
        Prepares the JSON data structure for the custom allocation widget.
        It includes all demand lines and their current target_qty.
        """
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
        data = {
            "meta": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "mode": self.env.context.get("default_partition_mode", "split"),
            },
            "tree": self._build_tree_recursive(root_line[0]),
            "demand_moves": self._format_demand(campaign),
        }
        # _logger.warning(json.dumps(data))
        return data

    @api.model
    def _build_tree_recursive(self, line: CampaignLine) -> dict[str, Any]:
        mos = line.production_ids
        planned = line.pre_buffer_qty
        done = sum(mos.mapped("qty_produced"))
        wip = line.committed_qty

        quantities = {
            "planned": 0,
            "done": done,
            "wip": wip,
            "floor": wip,
            "initial_planned": planned,
        }

        data = {
            "line_id": line.id,
            "product_name": line.product_id.display_name,
            "product_id": line.product_id.id,
            "uom": line.product_id.uom_id.display_name,
            "quantities": quantities,
            "ratio": line._get_downstream_factor(),
            "upstream_branches": [
                self._build_tree_recursive(parent) for parent in line.upstream_line_ids
            ],
        }

        return data

    @api.model
    def _format_demand(self, campaign: MrpCampaign) -> list[dict[str, Any]]:
        """Aggregates demand from SOs/Deliveries linked to the campaign lines"""
        moves: list[dict[str, Any]] = []
        for demand in campaign.demand_line_ids:
            sorted_proxies = demand.demand_proxy_ids.sorted(
                key=lambda proxy: (
                    proxy.move_id.priority,
                    proxy.move_id.date_deadline or proxy.move_id.date,
                )
            )

            for proxy in sorted_proxies:
                move = proxy.move_id
                order_ref = move.group_id.sale_id.client_order_ref
                moves.append(
                    {
                        "proxy_id": proxy.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_name": move.product_id.display_name,
                        "origin": move.origin or move.picking_id.name,
                        "customer_ref": order_ref,
                        "customer": move.partner_id.name or "Internal",
                        "fulfilled_qty": 0,
                        "target_qty": proxy.promised_qty,
                        "uom": move.product_uom.display_name,
                        "deadline": move.date_deadline.strftime("%Y-%m-%d")
                        if move.date_deadline
                        else False,
                    }
                )

        return moves

    def action_partition_campaign(self):  # pragma: no coverage
        self.ensure_one()
        data = json.loads(self.partition_data_json)
        prod_lines = self._validate_json_production(data)
        demand_lines = self._validate_json_demand(data)

        # Deltas represent the difference between the initial campaign
        # and the input by the user.
        # as such, they are the quantities to backorder.
        prod_deltas = self._get_deltas_production(prod_lines)
        demand_deltas = self._get_deltas_demand(demand_lines)

        dest_campaign = self.with_context(
            campaign_skip_mo_adjustment=True
        ).campaign_id._split(prod_deltas, demand_deltas)

        # Trigger re-synchronization of MOs for the original campaign
        self.campaign_id._resync_mos()

        # For the destination campaign, we need to build its tree and create initial MOs
        if dest_campaign:
            dest_campaign.action_plan()

        return {"type": "ir.actions.act_window_close"}

    def _validate_json_production(self, data: dict[str, Any]) -> dict[int, tuple]:
        tree: dict = data.get("tree", None)
        if not tree:
            raise ValidationError(
                _("Malformed Data: missing 'tree' attribute in JSON.")
            )

        def get_all_lines(root: dict, result: dict | None = None) -> dict[int, dict]:
            if result is None:
                result = {}

            node_data = {k: v for k, v in root.items() if k != "upstream_branches"}
            result[node_data["line_id"]] = node_data
            branches = root.get("upstream_branches", [])
            for branch in branches:
                get_all_lines(branch, result)

            return result

        campaign_lines: dict[int, dict] = get_all_lines(tree)
        records = self.env["mrp.campaign.line"].browse(campaign_lines.keys())

        if set(campaign_lines.keys()) != set(records.exists().mapped("id")):
            if len(set(campaign_lines.keys())) != len(
                set(records.exists().mapped("id"))
            ):
                raise ValidationError(_("Not all campaign line exists"))

        if not all([record.campaign_id == self.campaign_id for record in records]):
            raise ValidationError(
                _("Not all campaign_line belong to the current campaign")
            )

        mapped_data = {}
        for record in records:
            mapped_data[record.id] = (record, campaign_lines[record.id])
        return mapped_data

    def _get_deltas_production(self, lines: dict[int, tuple]) -> dict[int, tuple]:
        deltas = {}
        for rec_id, data in lines.items():
            line = data[0]
            intent = data[1]
            quantities = intent["quantities"]

            if line.product_id.id != intent["product_id"]:
                raise ValidationError(_("Line product and intent product do not match"))
            if quantities["planned"] < line.committed_qty:
                values = {
                    "product": intent["product_name"],
                    "plan": quantities["planned"],
                    "actual": line.committed_qty,
                }
                raise ValidationError(
                    _(
                        "Cannot plan less of %(product)s than currently "
                        "produced quantity (%(plan)f < %(actual)f) " % values
                    )
                )
            delta = line.pre_buffer_qty - quantities["planned"]
            if delta == 0:
                continue
            deltas[rec_id] = (line, delta)

        return deltas

    def _validate_json_demand(self, data: dict[str, Any]) -> dict[int, tuple]:
        demand_data = data.get("demand_moves", None)
        if demand_data is None:
            raise ValidationError(
                _("Malformed data: missing 'demand_moves' attribute in JSON.")
            )
        mapped_proxy = {v["proxy_id"]: v for v in demand_data}
        proxies = self.env["mrp.campaign.demand.proxy"].browse(mapped_proxy.keys())

        if set(mapped_proxy.keys()) != set(proxies.exists().ids):
            raise ValidationError(_("Not all proxies could be found in the database."))

        if not all(proxies.mapped(lambda proxy: proxy.campaign_id == self.campaign_id)):
            bad_proxies = [
                proxy.id for proxy in proxies if proxy.campaign_id != self.campaign_id
            ]
            raise ValidationError(
                _(
                    "Proxies %s are not associated with the current campaign",
                    bad_proxies,
                )
            )

        mapped_data = {}
        mapped_data = {proxy.id: (proxy, mapped_proxy[proxy.id]) for proxy in proxies}
        return mapped_data

    def _get_deltas_demand(self, lines: dict[int, tuple]) -> dict[int, tuple]:
        deltas = {}
        for rec_id, data in lines.items():
            rec = data[0]
            intent = data[1]
            current_promised_qty = rec.promised_qty
            intended_promised_qty = intent["fulfilled_qty"]

            if intended_promised_qty < 0:
                raise ValidationError(
                    _(
                        "Trying to assign a negative quantity (%(qty)d) to a SO."
                        % {"qty": intended_promised_qty}
                    )
                )

            if intended_promised_qty > rec.upstream_qty:
                raise ValidationError(
                    _(
                        "Trying to assign a larger quantity "
                        "than required (%(assigned)d > %(demand)d)."
                        % {
                            "assigned": intended_promised_qty,
                            "demand": rec.upstream_qty,
                        }
                    )
                )

            delta = current_promised_qty - intended_promised_qty

            if delta == 0:
                continue

            deltas[rec_id] = (rec, delta)
        return deltas
