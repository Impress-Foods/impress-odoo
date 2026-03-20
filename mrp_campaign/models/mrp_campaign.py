import colorsys
import random

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    workflow_type = fields.Selection([], copy=True, index=True)

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
        return self.env["ir.sequence"].next_by_code("mrp.campaign") or _("New")

    @api.model
    def _generate_color(self) -> str:  # pragma: no coverage
        hue, sat, lum = random.random(), random.uniform(0.4, 0.8), 0.5
        rgb: tuple[float, float, float] = colorsys.hls_to_rgb(hue, sat, lum)
        r, g, b = (round(rgb[0] * 255), round(rgb[1] * 255), round(rgb[2] * 255))
        return f"#{r:02x}{g:02x}{b:02x}"

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _get_demand_wizard_model(self) -> str:
        raise ValidationError(_("No wizard is implemented!"))

    def _get_partition_wizard_model(self) -> str:
        raise ValidationError(_("No partition wizard is implemented!"))

    def _has_demands_to_partition(self) -> bool:
        return False

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_plan(self) -> None:
        for campaign in self.filtered(lambda x: x.state == "draft"):
            if not campaign.demand_line_ids:
                raise UserError(
                    _(
                        "Cannot confirm campaign %s without any demand.",
                        campaign.name,
                    )
                )

            campaign._construct_tree_from_demand()

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
                [
                    "&",
                    ("campaign_id", "=", campaign.id),
                    ("created_by_campaign", "=", True),
                ]
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
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "tree,form",
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
            "domain": [("id", "in", self.backorder_campaign_ids.ids)],
            "view_mode": "tree,form",
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
        wizard_model = self._get_demand_wizard_model()
        return {
            "type": "ir.actions.act_window",
            "name": "Add Demand to Campaign",
            "res_model": wizard_model,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_campaign_id": self.id,
            },
        }

    def action_open_split_wizard(self) -> dict:
        return self.action_open_partition_wizard(mode="split")

    def action_bo(self) -> dict:
        return self.action_open_partition_wizard(mode="backorder")

    def action_open_partition_wizard(self, mode: str = "split") -> dict:
        self.ensure_one()
        wizard_model = self._get_partition_wizard_model()
        if mode == "split":
            if self.state not in ["draft", "plan"]:
                raise ValidationError(
                    _("Only campaigns in 'Draft' or 'Planned' state can be split")
                )
            name = _("Split Campaign: %s", self.name)
        elif mode == "backorder":
            name = _("Backorder Campaign: %s", self.name)
        else:
            raise ValueError(_("Invalid partition mode"))

        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": wizard_model,
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
                [
                    ("date_start", "!=", rec.date_planned_start),
                    ("state", "in", ["draft", "confirmed"]),
                ]
            )
            mos_to_sync.write({"date_start": rec.date_planned_start})

    def _sync_lot_on_productions(self, lot_name) -> None:
        self.ensure_one()
        productions = self.production_ids.filtered(
            lambda p: (
                p.state not in ["done", "cancel"]
                and (not p.lot_producing_id or p.lot_producing_id.name != lot_name)
            )
        )
        if not productions:
            return

        products = productions.mapped("product_id")
        existing_lots = self.env["stock.lot"].search(
            [
                ("name", "=", lot_name),
                ("product_id", "in", products.ids),
                ("company_id", "=", self.company_id.id),
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
            prods.with_context(syncing_lot=True).write({"lot_producing_id": lot.id})

    def _resync_mos(self) -> None:
        self.ensure_one()
        self.line_ids.mapped("qty")
        for line in self.line_ids.sorted("sequence"):
            if line.productions_created:
                line._adjust_mos(line.qty)

    def _split(self, demand_split_instructions) -> "MrpCampaign":
        """
        Execute the split based on bridge-provided instructions.

        Args:
            demand_split_instructions: {
                demand_id: {
                    'qty': float,      # New qty for this campaign
                    'bo_qty': float,   # Qty for backorder campaign
                }
            }

        Returns:
            Newly created backorder campaign
        """
        self.ensure_one()

        demand_ids = list(demand_split_instructions.keys())
        demands = self.env["mrp.campaign.demand"].browse(demand_ids)
        demands_not_in_campaign = demands.filtered_domain(
            [("id", "in", demand_ids), ("campaign_id", "!=", self.id)]
        )
        if demands_not_in_campaign:
            raise ValidationError(
                _(
                    "All demands must belong to this campaign: %s",
                    demands_not_in_campaign,
                )
            )

        bo_campaign = self.copy(default={"bo_source_id": self.id})

        for demand_id, instructions in demand_split_instructions.items():
            demand = demands.browse(demand_id)
            qty = instructions.get("qty", 0)
            bo_qty = instructions.get("bo_qty", 0)

            demand.write({"target_qty": qty})

            if bo_qty > 0:
                demand.with_context(campaign_skip_line=True).copy(
                    default={
                        "campaign_id": bo_campaign.id,
                        "campaign_line_id": False,
                        "target_qty": bo_qty,
                    }
                )

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
            raise UserError(_("Can't delete a campaign in progress!"))
        if any(rec.state in ["done"] for rec in self):
            raise UserError(_("Can't delete a completed campaign!"))

    def unlink(self) -> bool:
        mos_to_unlink = self.mapped("production_ids").filtered_domain(
            [("state", "in", ["draft"])]
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
