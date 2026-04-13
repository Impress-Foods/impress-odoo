import colorsys
import random

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain


class MrpCampaign(models.Model):
    _name = "mrp.campaign"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Manufacturing Campaign"
    _order = "date_planned_start desc,sequence desc"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Campaign Reference",
        required=True,
        copy=False,
        default=lambda self: self._get_name_seq(),
    )
    sequence = fields.Integer()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("plan", "Planned"),
            ("confirm", "Confirmed"),
            ("progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        compute="_compute_state",
        string="Status",
        default="draft",
        store=True,
    )
    campaign_color = fields.Char(default=lambda self: self._generate_color())

    workflow_type = fields.Selection([("direct", "Direct")], copy=True, index=True)

    date_planned_start = fields.Date(
        string="Scheduled Date", required=True, default=fields.Date.today
    )

    product_id = fields.Many2one(
        "product.product",
        string="Intermediate Product",
        required=True,
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
    )
    buffer_percent = fields.Float(
        compute="_compute_buffer_percent", store=True, readonly=False
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    lot_name = fields.Char()
    override_batch_size = fields.Boolean()
    batch_size = fields.Float()

    demand_line_ids = fields.One2many("mrp.campaign.demand", "campaign_id")
    line_ids = fields.One2many("mrp.campaign.line", "campaign_id")

    production_ids = fields.One2many("mrp.production", "campaign_id")
    production_count = fields.Integer(compute="_compute_production_count")

    backorder_campaign_ids = fields.One2many("mrp.campaign", "bo_source_id")
    bo_count = fields.Integer(compute="_compute_bo_count")
    bo_source_id = fields.Many2one("mrp.campaign")

    is_out_of_sync = fields.Boolean(compute="_compute_is_out_of_sync", store=True)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("line_ids.is_out_of_sync")
    def _compute_is_out_of_sync(self) -> None:
        for rec in self:
            rec.is_out_of_sync = any(rec.line_ids.mapped("is_out_of_sync"))

    @api.depends("backorder_campaign_ids")
    def _compute_bo_count(self) -> None:  # pragma: no coverage
        for rec in self:
            rec.bo_count = len(rec.backorder_campaign_ids)

    @api.depends("production_ids", "production_ids.state", "production_count")
    def _compute_state(self) -> None:
        for rec in self:
            if rec.production_count == 0:
                rec.state = "draft"
            elif any(
                prod.state in ["progress", "to_close"] for prod in rec.production_ids
            ):
                rec.state = "progress"
            elif any(prod.state in ["confirmed"] for prod in rec.production_ids):
                rec.state = "confirm"
            elif all(prod.state in ["cancel"] for prod in rec.production_ids):
                rec.state = "cancel"
            elif all(prod.state in ["done", "cancel"] for prod in rec.production_ids):
                rec.state = "done"
            else:
                rec.state = "plan"

    @api.depends("production_ids")
    def _compute_production_count(self) -> None:
        for rec in self:
            rec.production_count = len(rec.production_ids)

    @api.depends("product_id")
    def _compute_buffer_percent(self) -> None:
        for rec in self:
            if rec.product_id:
                rec.buffer_percent = rec.product_id.campaign_buffer_percent
            else:
                rec.buffer_percent = 0

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _get_name_seq(self) -> str:  # pragma: no coverage
        return self.env["ir.sequence"].next_by_code("mrp.campaign") or self.env._("New")

    @api.model
    def _generate_color(self) -> str:  # pragma: no coverage
        hue, sat, lum = random.random(), random.uniform(0.4, 0.8), 0.5
        rgb: tuple[float, float, float] = colorsys.hls_to_rgb(hue, sat, lum)
        r, g, b = (round(rgb[0] * 255), round(rgb[1] * 255), round(rgb[2] * 255))
        return f"#{r:02x}{g:02x}{b:02x}"

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _has_demands_to_partition(self) -> bool:
        return False

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_plan(self) -> None:
        for campaign in self.filtered(lambda x: x.state == "draft"):
            if not campaign.demand_line_ids:
                raise UserError(
                    self.env._(
                        "Cannot confirm campaign %s without any demand.",
                        campaign.name,
                    )
                )

            campaign.construct_tree()
            for line in campaign.line_ids:
                line.make_production_order()

    def action_confirm(self) -> None:
        for campaign in self.filtered(lambda x: x.state == "plan"):
            end_mos_to_confirm = campaign.production_ids.filtered(
                lambda mo: mo.state == "draft"
            )
            if end_mos_to_confirm:
                end_mos_to_confirm.action_confirm()

    def action_reset(self) -> None:
        for campaign in self.filtered(lambda c: c.state in ["plan", "confirm"]):
            productions = campaign.production_ids.filtered_domain(
                Domain("campaign_id", "=", campaign.id)
                & Domain("created_by_campaign", "=", True)
            )
            if productions:
                productions.action_cancel()
                productions.unlink()
            campaign.line_ids.unlink()
            campaign._compute_state()

    def action_view_mos(self) -> dict:  # pragma: no coverage
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Production orders for %s" % self.name,
            "res_model": "mrp.production",
            "domain": Domain("id", "in", self.production_ids.ids),
            "view_mode": "list,form",
            "target": "current",
        }

    def action_view_bos(self) -> dict:  # pragma: no coverage
        self.ensure_one()
        if self.bo_count == 1:
            return {
                "type": "ir.actions.act_window",
                "name": "Backorders for %s" % self.name,
                "res_model": "mrp.campaign",
                "res_id": self.backorder_campaign_ids[0].id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": "Backorders for %s" % self.name,
            "res_model": "mrp.campaign",
            "domain": Domain("id", "in", self.backorder_campaign_ids.ids),
            "view_mode": "list,form",
            "target": "current",
        }

    def action_view_source(self) -> dict:  # pragma: no coverage
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.bo_source_id.name,
            "res_model": "mrp.campaign",
            "res_id": self.bo_source_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_add_demand_wizard(self) -> dict:
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Add Demand to Campaign",
            "res_model": "mrp.campaign.wizard.creator",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_campaign_id": self.id,
            },
        }

    def action_open_split_wizard(self) -> dict:
        self.ensure_one()
        return self.action_open_partition_wizard(mode="split")

    def action_bo(self) -> dict:
        self.ensure_one()
        return self.action_open_partition_wizard(mode="backorder")

    def action_open_partition_wizard(self, mode: str = "split") -> dict:
        self.ensure_one()
        if mode == "split":
            if self.state not in ["draft", "plan"]:
                raise ValidationError(
                    self.env._(
                        "Only campaigns in 'Draft' or 'Planned' state can be split"
                    )
                )
            name = self.env._("Split Campaign: %s", self.name)
        elif mode == "backorder":
            name = self.env._("Backorder Campaign: %s", self.name)
        else:
            raise ValueError(self.env._("Invalid partition mode"))

        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "mrp.campaign.wizard.partition",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": "mrp.campaign",
                "default_partition_mode": mode,
                "dialog_size": "xl",
            },
        }

    def action_sync_mos(self):  # pragma: no coverage
        for rec in self:
            rec._resync_mos()

    # -------------------------------------------------------------------------
    # BUSINESS LOGIC
    # -------------------------------------------------------------------------
    def construct_tree(self) -> None:
        for rec in self:
            rec._construct_tree_from_demand()

    def _construct_tree_from_demand(self, propagate: bool = True) -> None:
        self.ensure_one()
        self.line_ids.unlink()

        created_lines = self.demand_line_ids.create_campaign_line()

        if propagate:
            for line in created_lines:
                line._construct_downstream_tree_line(depth=0)

    def _sync_mo_start_dates(self) -> None:
        for rec in self:
            mos_to_sync = rec.production_ids.filtered_domain(
                Domain("date_start", "!=", rec.date_planned_start)
                & Domain("state", "in", ["draft", "confirmed"])
            )
            mos_to_sync.write({"date_start": rec.date_planned_start})

    def _sync_lot_on_productions(self, lot_name) -> None:
        self.ensure_one()
        productions = self.production_ids.filtered(
            lambda p: (
                p.state not in ["done", "cancel"]
                and (
                    not p.lot_producing_ids or p.lot_producing_ids[:1].name != lot_name
                )
            )
        )
        if not productions:
            return

        products = productions.mapped("product_id")
        existing_lots = self.env["stock.lot"].search(
            [
                Domain("name", "=", lot_name)
                & Domain("product_id", "in", products.ids)
                & Domain("company_id", "=", self.company_id.id)
            ]
        )
        lots_by_product = {lot.product_id.id: lot for lot in existing_lots}

        prods_to_update_by_lot = {}
        for production in productions:
            product = production.product_id
            lot = lots_by_product.get(product.id)
            if not lot:
                lot = self.env["stock.lot"].create(
                    {
                        "name": lot_name,
                        "product_id": product.id,
                        "company_id": self.company_id.id,
                    }
                )
                lots_by_product[product.id] = lot

            prods_to_update_by_lot.setdefault(lot, self.env["mrp.production"])
            prods_to_update_by_lot[lot] |= production

        for lot, prods in prods_to_update_by_lot.items():
            prods.with_context(syncing_lot=True).write(
                {"lot_producing_ids": [Command.clear(), Command.link(lot.id)]}
            )

    def _resync_mos(self) -> None:
        self.ensure_one()
        for line in self.line_ids.sorted("sequence"):
            if line.productions_created:
                line._adjust_mos(line.qty)

    def _split(self, target_qtys: dict) -> "MrpCampaign":
        """Execute the split based on target quantity instructions.

        Args:
            target_qtys: flat dict {target_id: final_promised_qty}
                - Targets in this dict with qty > 0 stay on original campaign
                - Targets NOT in this dict go to backorder
                - Targets with qty = 0 go to backorder

        Returns:
            Newly created backorder campaign
        """
        self.ensure_one()

        targets = self.env["mrp.campaign.demand.target"].browse(
            list(target_qtys.keys())
        )
        campaign_targets = self.env["mrp.campaign.demand.target"].search(
            Domain("campaign_id", "=", self.id)
        )
        invalid_targets = targets - campaign_targets
        if invalid_targets:
            raise ValidationError(
                self.env._(
                    "Targets %s do not belong to this campaign.", invalid_targets
                )
            )

        demands = self.demand_line_ids

        # We BO targets that:
        # - Have a target_qty == 0
        # - have a target_qty < promised_qty
        # - absent (since that means a target_qty == 0)

        absent_targets = campaign_targets - targets
        zero_targets = targets.filtered(lambda target: target_qtys[target.id] == 0)
        under_targets = targets.filtered(
            lambda target: target_qtys[target.id] < target.promised_qty
        )

        targets_to_bo = absent_targets | zero_targets | under_targets

        if not targets_to_bo:
            return self.env["mrp.campaign"]

        bo_campaign = self.copy(
            default={"bo_source_id": self.id, "demand_line_ids": [], "line_ids": []}
        )

        for demand in demands:
            if demand.target_ids <= (zero_targets | absent_targets):
                if demand.campaign_line_id.productions_created:
                    demand.campaign_line_id._adjust_mos(0)
                demand.campaign_line_id.unlink()
                demand.campaign_id = bo_campaign

            else:
                targets_to_bo_for_demand = targets_to_bo.filtered_domain(
                    Domain("demand_id", "=", demand.id)
                )
                if not targets_to_bo_for_demand:
                    continue
                bo_demand = (
                    self.env["mrp.campaign.demand"]
                    .with_context(campaign_skip_line=True)
                    .create(
                        {
                            "campaign_id": bo_campaign.id,
                            "product_id": demand.product_id.id,
                            "bom_id": demand.bom_id.id,
                        }
                    )
                )

                for target in targets_to_bo_for_demand:
                    if target in absent_targets | zero_targets:
                        target.demand_id = bo_demand
                    else:
                        target_qty = target_qtys[target.id]
                        diff = target.promised_qty - target_qty
                        target.promised_qty = target_qty
                        target.copy({"promised_qty": diff, "demand_id": bo_demand.id})

        if bo_campaign.demand_line_ids:
            bo_campaign._construct_tree_from_demand()
            bo_campaign.action_plan()

        self._resync_mos()
        self._after_split(bo_campaign)

        return bo_campaign

    def _after_split(self, backorder_campaign) -> None:
        """Hook for bridges to handle post-split operations."""
        pass

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.ondelete(at_uninstall=False)
    def _unlink_if_campaign_inactive(self) -> None:
        if any(rec.state in ["progress"] for rec in self):
            raise UserError(self.env._("Can't delete a campaign in progress!"))
        if any(rec.state in ["done"] for rec in self):
            raise UserError(self.env._("Can't delete a completed campaign!"))

    def unlink(self) -> bool:
        mos_to_unlink = self.mapped("production_ids").filtered_domain(
            Domain("state", "in", ["draft"])
        )
        mos_to_unlink.unlink()
        self.mapped("demand_line_ids").unlink()
        return super().unlink()

    def write(self, vals) -> bool:
        res = super().write(vals)

        if "lot_name" in vals:
            for rec in self:
                rec._sync_lot_on_productions(vals["lot_name"])

        if "date_planned_start" in vals:
            self._sync_mo_start_dates()
        return res
