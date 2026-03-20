import json

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class MrpCampaignPartitionWizardProductionBilling(models.TransientModel):
    _name = "mrp.campaign.partition.wizard.production_billing"
    _description = "Wizard to Partition an MRP Campaign (Production Billing)"

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

    def _format_demand(self, campaign) -> list:
        """Aggregates demand from billing sale orders."""
        moves = []
        for demand in campaign.demand_line_ids:
            for proxy in demand.billing_proxy_ids:
                moves.append(proxy._get_partition_wizard_fields())
        return moves

    def _make_partition_json(self, campaign) -> dict:
        """Prepares the JSON data structure for the partition widget."""
        campaign.ensure_one()
        return {
            "meta": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "mode": self.env.context.get("default_partition_mode", "split"),
            },
            "demand_moves": self._format_demand(campaign),
        }

    def _validate_json_demand(self, data: dict) -> dict:
        demand_data = data.get("demand_moves", [])
        mapped_proxy = {v["proxy_id"]: v for v in demand_data}
        proxies = self.env["mrp.campaign.demand.billing_proxy"].browse(
            mapped_proxy.keys()
        )

        if set(mapped_proxy.keys()) != set(proxies.exists().ids):
            raise ValidationError(_("Not all proxies could be found."))

        bad_proxies = [
            proxy for proxy in proxies if proxy.campaign_id != self.campaign_id
        ]
        if bad_proxies:
            raise ValidationError(
                _(
                    "Proxies %(proxies)s are not associated with the current campaign",
                    proxies=bad_proxies,
                )
            )

        return {proxy.id: (proxy, mapped_proxy[proxy.id]) for proxy in proxies}

    def _get_deltas_demand(self, lines: dict) -> dict:
        deltas = {}
        for rec_id, (rec, intent) in lines.items():
            intended_qty = intent.get("fulfilled_qty", 0)
            if intended_qty < 0:
                raise ValidationError(
                    _(
                        "Trying to assign a negative quantity (%(qty)d) to a SO.",
                        qty=intended_qty,
                    )
                )
            if intended_qty > rec.promised_qty:
                raise ValidationError(
                    _(
                        "Trying to assign a larger quantity "
                        "than required (%(intended)d > %(prom)d).",
                        intedned=intended_qty,
                        prom=rec.promised_qty,
                    )
                )
            delta = rec.promised_qty - intended_qty
            if delta != 0:
                deltas[rec_id] = (rec, delta)
        return deltas

    def _compute_demand_split_instructions(self, demand_deltas: dict) -> dict:
        instructions = {}
        for _proxy_id, (proxy, delta) in demand_deltas.items():
            demand = proxy.demand_id
            if demand.id not in instructions:
                instructions[demand.id] = {"qty": demand.target_qty, "bo_qty": 0.0}
            if delta > 0:
                instructions[demand.id]["qty"] -= delta
                instructions[demand.id]["bo_qty"] += delta
        return instructions

    def action_partition_campaign(self):
        self.ensure_one()
        data = json.loads(self.partition_data_json or "{}")
        demand_lines = self._validate_json_demand(data)
        demand_deltas = self._get_deltas_demand(demand_lines)
        demand_split_instructions = self._compute_demand_split_instructions(
            demand_deltas
        )

        self.campaign_id._split(demand_split_instructions)

        return {"type": "ir.actions.act_window_close"}
