import colorsys
import logging
import random
from datetime import datetime, time, timedelta
from typing import Literal

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.stock.models.stock_rule import StockRule

from .procurement import Procurement

_logger = logging.getLogger(__name__)


class MrpCampaign(models.Model):
    _name = "mrp.campaign"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Manufacturing Campaign"
    _order = "date_planned_start desc,sequence desc"

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
    )
    campaign_color = fields.Char(default=lambda self: self._generate_color())

    bucket_start_date = fields.Date()
    bucket_end_date = fields.Date(compute="_compute_bucket_end_date")
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
        compute="_compute_buffer_percent",
        inverse="_inverse_buffer_percent",
        store=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    lot_name = fields.Char()
    override_batch_size = fields.Boolean()
    batch_size = fields.Float()

    demand_line_ids = fields.One2many("mrp.campaign.demand", "campaign_id")

    line_ids = fields.One2many("mrp.campaign.line", "campaign_id")

    production_ids = fields.One2many("mrp.production", "campaign_id")
    production_count = fields.Integer(compute="_compute_production_count")

    backorder_campaign_ids = fields.One2many("mrp.campaign", "bo_source")
    bo_count = fields.Integer(compute="_compute_bo_count")
    bo_source = fields.Many2one("mrp.campaign")

    @api.depends("backorder_campaign_ids")
    def _compute_bo_count(self):
        for rec in self:
            rec.bo_count = len(rec.backorder_campaign_ids)

    @api.depends("production_ids", "production_ids.state")
    def _compute_state(self):
        for rec in self:
            if rec.production_count == 0:
                rec.state = "draft"
            elif any(
                [prod.state in ["progress", "to_close"] for prod in rec.production_ids]
            ):
                rec.state = "progress"
            elif any([prod.state in ["confirmed"] for prod in rec.production_ids]):
                rec.state = "confirm"
            elif all([prod.state in ["cancelled"] for prod in rec.production_ids]):
                rec.state = "cancelled"
            elif all(
                [prod.state in ["done", "cancelled"] for prod in rec.production_ids]
            ):
                rec.state = "done"
            else:
                rec.state = "plan"

    @api.depends("production_ids")
    def _compute_production_count(self):
        for rec in self:
            rec.production_count = len(rec.production_ids)

    @api.depends("product_id")
    def _compute_buffer_percent(self):
        for rec in self:
            if rec.product_id:
                rec.buffer_percent = rec.product_id.campaign_buffer_percent
            else:
                rec.buffer_percent = 0

    def _inverse_buffer_percent(self):
        return

    @api.depends(
        "bucket_start_date",
        "product_id.product_tmpl_id.campaign_bucket_type",
        "product_id.product_tmpl_id.campaign_bucket_size",
    )
    def _compute_bucket_end_date(self) -> None:
        for rec in self:
            if not rec.bucket_start_date:
                rec.bucket_end_date = False
                return
            bucket_period: Literal[
                "day", "week", "month", "year"
            ] = rec.product_id.campaign_bucket_type
            bucket_length: int = rec.product_id.campaign_bucket_size

            delta: timedelta = timedelta(days=1)

            match bucket_period:
                case "day":
                    delta = timedelta(days=bucket_length)
                case "week":
                    delta = timedelta(days=bucket_length * 7)
                case "month":
                    delta = timedelta(days=bucket_length * 30)
                case "year":
                    delta = timedelta(days=bucket_length * 365)
                case _:
                    delta = timedelta(days=bucket_length)

            rec.bucket_end_date = rec.bucket_start_date + delta

    def write(self, vals):
        # Store old date_planned_starts values (which will be Date objects after Part 0)
        old_date_planned_starts = {rec.id: rec.date_planned_start for rec in self}

        res = super().write(vals)

        if "date_planned_start" in vals:
            for rec in self:
                # Only proceed if date_planned_start is set, there are MOs,
                # and the DATE part of date_planned_start has actually changed.
                if (
                    rec.date_planned_start
                    and rec.production_ids
                    and (
                        not old_date_planned_starts.get(rec.id)
                        or old_date_planned_starts[rec.id] != rec.date_planned_start
                    )
                ):
                    new_campaign_date = (
                        rec.date_planned_start
                    )  # This is now a Date object

                    for mo in rec.production_ids:
                        # Preserve MO's original time, apply new campaign day
                        # If mo.date_start is not set,
                        # default to time.min (beginning of day)
                        mo_original_time = (
                            mo.date_start.time() if mo.date_start else time.min
                        )
                        mo_new_date_start = datetime.combine(
                            new_campaign_date, mo_original_time
                        )
                        mo_new_date_deadline = datetime.combine(
                            new_campaign_date, time.max
                        )

                        # Write only if a change is needed to
                        # avoid unnecessary database updates
                        if (
                            mo.date_start != mo_new_date_start
                            or mo.date_deadline != mo_new_date_deadline
                        ):
                            mo.write(
                                {
                                    "date_start": mo_new_date_start,
                                    "date_deadline": mo_new_date_deadline,
                                }
                            )
        return res

    def _compute_available_anchor(self) -> float:
        self.ensure_one()

    def _sync_date_planned_start(self):
        """
        Synchronizes date_planned_start and bucket_start_date based on the earliest
        date_deadline of all demand moves linked to the campaign lines. This ensures
        the campaign is scheduled to satisfy the earliest demand within it.
        """
        for campaign in self:
            if not campaign.line_ids:
                continue

            all_move_dest_deadlines = campaign.line_ids.mapped(
                "move_dest_ids.date_deadline"
            )
            if not all_move_dest_deadlines:
                continue

            min_demand_date_deadline = min(all_move_dest_deadlines).date()

            # If the campaign's planned date is later than the earliest demand,
            # pull it back. This ensures all demands in the campaign are met on time.
            # We check for a planned date to allow for manual setting, but if any
            # demand is earlier, we must respect it.
            if (
                not campaign.date_planned_start
                or campaign.date_planned_start > min_demand_date_deadline
            ):
                campaign.date_planned_start = min_demand_date_deadline

    def _sync_lot_on_productions(self, lot_name, productions_to_skip=None):
        self.ensure_one()
        if productions_to_skip is None:
            productions_to_skip = self.env["mrp.production"]

        productions_to_update = self.production_ids - productions_to_skip

        for production in productions_to_update:
            if (
                production.lot_producing_id
                and production.lot_producing_id.name == lot_name
            ):
                continue

            Lot = self.env["stock.lot"]
            lot_to_assign = Lot.search(
                [
                    ("name", "=", lot_name),
                    ("product_id", "=", production.product_id.id),
                    ("company_id", "=", production.company_id.id),
                ],
                limit=1,
            )

            if not lot_to_assign:
                lot_to_assign = Lot.create(
                    {
                        "name": lot_name,
                        "product_id": production.product_id.id,
                        "company_id": production.company_id.id,
                    }
                )

            production.with_context(syncing_lot=True).write(
                {"lot_producing_id": lot_to_assign.id}
            )

    def construct_tree(self):
        """
        Main method to initiate the construction of the campaign production tree.
        """
        for rec in self:
            rec._construct_tree_from_demand()

    def _construct_tree_from_demand(self):
        """
        Constructs the initial level of the campaign production tree
        from demand lines and then recursively builds the downstream tree.
        """
        self.ensure_one()
        self.line_ids.unlink()

        created_lines = self.env["mrp.campaign.line"]
        for demand in self.demand_line_ids:
            # Determine the BOM for the demand product
            demand_bom = (
                demand.bom_id
                or self.env["mrp.bom"]._bom_find(products=demand.product_id)[
                    demand.product_id
                ]
            )

            existing_line = self.line_ids.filtered(
                lambda line, demand=demand, demand_bom=demand_bom: (
                    line.product_id == demand.product_id and line.bom_id == demand_bom
                )
            )
            if existing_line:
                existing_line.qty += demand.qty
                created_lines |= existing_line
            else:
                new_line = self.env["mrp.campaign.line"].create(
                    {
                        "campaign_id": self.id,
                        "product_id": demand.product_id.id,
                        "bom_id": demand_bom.id,
                        "qty": demand.qty,
                    }
                )
                created_lines |= new_line

            demand.campaign_line_id = new_line or existing_line

        for line in created_lines:
            line._construct_downstream_tree_line(depth=0)

    def action_plan(self):
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

    def action_confirm(self):
        for campaign in self.filtered(lambda x: x.state == "plan"):
            end_mos_to_confirm = campaign.production_ids.filtered(
                lambda mo: mo.state == "draft"
            )
            if end_mos_to_confirm:
                end_mos_to_confirm.with_context(
                    ignore_campaign_procurement=True
                ).action_confirm()

    def action_reset(self):
        """
        Resets a confirmed campaign back to draft, deleting any manufacturing
        orders and stock moves that were created by the confirmation process.
        """
        for campaign in self.filtered(lambda c: c.state in ["plan", "confirm"]):
            # Find and cancel any manufacturing orders created for this campaign
            productions = self.env["mrp.production"].search(
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

    def action_bo(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("backorder Campaign: %s", self.name),
            "res_model": "mrp.campaign.backorder.wizard",
            "view_mode": "form",
            "target": "new",  # Keep it as 'new' for a standard modal window
            "context": {
                "active_id": self.id,
                "active_model": "mrp.campaign",
            },
        }

    def action_view_mos(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "tree,form",
            "target": "current",
        }

    def action_view_bos(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "domain": [("id", "in", self.backorder_campaign_ids.ids)],
            "view_mode": "tree,form",
            "target": "current",
        }

    def action_open_add_demand_wizard(self):
        self.ensure_one()

        anchor_product = self.product_id

        # 1. Find all products that use this anchor by traversing BoMs upwards
        all_descendants = self.env["product.product"].browse(anchor_product.id)
        products_to_check = self.env["product.product"].browse(anchor_product.id)
        while products_to_check:
            boms = (
                self.env["mrp.bom.line"]
                .search([("product_id", "in", products_to_check.ids)])
                .mapped("bom_id")
            )
            parent_products = boms.mapped("product_id")
            parent_from_template = boms.mapped("product_tmpl_id").mapped(
                "product_variant_ids"
            )
            all_parents = parent_products | parent_from_template
            newly_found = all_parents - all_descendants
            if not newly_found:
                break
            all_descendants |= newly_found
            products_to_check = newly_found

        # 2. Find potential demand moves for these products
        potential_moves = self.env["stock.move"].search(
            [
                ("product_id", "in", all_descendants.ids),
                (
                    "state",
                    "in",
                    ["confirmed", "waiting", "partially_available", "assigned"],
                ),
                ("created_production_id", "=", False),
                ("production_id", "=", False),
            ]
        )

        # 3. Find moves already in any campaign to exclude them
        all_campaign_lines = self.env["mrp.campaign.demand"].search([])
        moves_in_campaigns = all_campaign_lines.mapped("move_dest_ids")

        # 4. Filter out moves already in other campaigns
        available_moves = potential_moves - moves_in_campaigns

        # 5. Return action to open the wizard
        return {
            "type": "ir.actions.act_window",
            "name": "Add Demand to Campaign",
            "res_model": "mrp.campaign.add.demand",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_campaign_id": self.id,
                "available_move_ids": available_moves.ids,
            },
        }

    def action_open_split_wizard(self):
        self.ensure_one()
        # Check if the campaign is in a splittable state (e.g., draft or review)
        if self.state not in ["draft", "plan"]:
            raise UserError(
                _("Only campaigns in 'Draft' or 'Planned' state can be split.")
            )

        # Check if there are any moves to split
        if not self.demand_line_ids or not self.demand_line_ids.mapped("move_dest_ids"):
            raise UserError(_("This campaign has no demand moves to split."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Split Campaign: %s", self.name),
            "res_model": "mrp.campaign.split.wizard",
            "view_mode": "form",
            "target": "new",  # Keep it as 'new' for a standard modal window
            "context": {
                "active_id": self.id,
                "active_model": "mrp.campaign",
            },
        }

    @api.model
    def _get_name_seq(self):
        """Generates a sequence number for the campaign name."""
        return self.env["ir.sequence"].next_by_code("mrp.campaign") or _("New")

    @api.model
    def _generate_color(self) -> str:
        hue, sat, lum = random.random(), random.uniform(0.4, 0.8), 0.5
        rgb: tuple[float, float, float] = colorsys.hls_to_rgb(hue, sat, lum)
        r, g, b = (round(rgb[0] * 255), round(rgb[1] * 255), round(rgb[2] * 255))
        return f"#{r:02x}{g:02x}{b:02x}"

    @api.model
    def _get_or_create_campaign_for_anchor(
        self, anchor_product, company, demand_date=None
    ):
        """
        Finds a Draft campaign that can accommodate the demand_date, or creates a
        new one. If no demand_date is provided, it falls back to finding the
        oldest existing campaign or creating a new one.
        """
        # If a demand date is specified, try to find a campaign bucket that fits it.
        if demand_date:
            campaigns = self.search(
                [
                    ("product_id", "=", anchor_product.id),
                    ("company_id", "=", company.id),
                    ("state", "in", ["draft", "review"]),
                ],
                order="date_planned_start asc",
            )

            for campaign in campaigns:
                if campaign.bucket_start_date and campaign.bucket_end_date:
                    if (
                        campaign.bucket_start_date
                        <= demand_date
                        < campaign.bucket_end_date
                    ):
                        _logger.info(
                            "Found exist campaign %s for anchor %s for demand date %s.",
                            campaign.name,
                            anchor_product.display_name,
                            demand_date,
                        )
                        return campaign

        # If no demand_date is provided or no suitable campaign was found,
        # create a new one.
        _logger.info(
            "No suitable campaign found for anchor %s and date %s. Creating a new one.",
            anchor_product.display_name,
            demand_date,
        )
        campaign = self.create(
            {
                "product_id": anchor_product.id,
                "company_id": company.id,
                "date_planned_start": demand_date,
                "bucket_start_date": demand_date,
            }
        )
        _logger.info(
            "Created new campaign %s for anchor %s for demand date %s.",
            campaign.name,
            anchor_product.display_name,
            demand_date,
        )
        return campaign

    @api.model
    def _collect_procurements(
        self, procurements: list[tuple[Procurement, "StockRule"]]
    ):
        """
        Main entry point from stock.rule interception.
        Takes a list of procurement objects and routes their moves to campaigns.
        """
        _logger.info(
            "Attempting to collect %d procurements into campaigns.", len(procurements)
        )

        procurements_by_anchor = {}
        for procurement, rule in procurements:
            anchor_product = procurement.product_id.anchor_product_id
            if not anchor_product:
                continue

            # Group by anchor to process procurements for the same anchor together
            key = (anchor_product, procurement.company_id)
            if key not in procurements_by_anchor:
                procurements_by_anchor[key] = []
            procurements_by_anchor[key].append((procurement, rule))

        for (
            anchor_product,
            _company,
        ), grouped_procurements in procurements_by_anchor.items():
            # Sort procurements by date to process them chronologically
            grouped_procurements.sort(
                key=lambda p: p[0].values.get("date_planned") or datetime.max
            )

            for procurement, _rule in grouped_procurements:
                # If the ignore_campaign_procurement flag is set in context,
                # this procurement originated from action_confirm_bulk
                #  and should be ignored
                # by our custom campaign logic.
                if self.env.context.get("ignore_campaign_procurement"):
                    _logger.info(
                        "Ignoring campaign procurement for %s.",
                        procurement.product_id.display_name,
                    )
                    continue

                _logger.info(
                    "Campaign route found for product %s through anchor %s.",
                    procurement.product_id.display_name,
                    anchor_product.display_name,
                )

                demand_moves = procurement.values.get("move_dest_ids")
                if not demand_moves:
                    _logger.warning(
                        (
                            "Procurement for product %s is being added to a "
                            "campaign without destination moves. "
                            "Traceability to the original demand "
                            "(e.g., Sales Order) may be lost."
                        ),
                        procurement.product_id.display_name,
                    )
                    demand_moves = self.env["stock.move"]

                demand_date = None
                if demand_moves:
                    # The demand date is the latest deadline
                    # of all moves in the procurement
                    demand_date = max(demand_moves.mapped("date_deadline")).date()

                # If no demand date could be determined, default to today's date.
                if not demand_date:
                    demand_date = fields.Date.context_today(self)

                # Determine the BoM
                bom = procurement.values.get("bom_id")
                if not bom:
                    bom = self.env["mrp.bom"]._bom_find(
                        products=procurement.product_id
                    )[procurement.product_id]

                # Search/Create Campaign for that Anchor
                campaign = self._get_or_create_campaign_for_anchor(
                    anchor_product=anchor_product,
                    company=procurement.company_id,
                    demand_date=demand_date,
                )

                # Update Reservoir (mrp.campaign.line), now unique by product AND bom
                campaign_line = campaign.demand_line_ids.filtered(
                    lambda line, p=procurement, b=bom: (
                        line.product_id == p.product_id and line.bom_id == b
                    )
                )

                if campaign_line:
                    # Add new demand moves to the existing ones.
                    campaign_line.move_dest_ids |= demand_moves
                    _logger.info(
                        (
                            "Updated line in campaign %s: %s (%s) by "
                            "adding demand for %f units."
                        ),
                        campaign.name,
                        campaign_line.product_id.display_name,
                        campaign_line.bom_id.code or "Default BoM",
                        procurement.product_qty,
                    )
                    campaign._sync_date_planned_start()

                else:
                    # Create a new line for this product/bom combination.
                    new_line = self.env["mrp.campaign.demand"].create(
                        {
                            "campaign_id": campaign.id,
                            "product_id": procurement.product_id.id,
                            "bom_id": bom.id if bom else False,
                            "move_dest_ids": [(6, 0, demand_moves.ids)],
                        }
                    )
                    _logger.info(
                        "Created new line in campaign %s: %s (%s), %f units.",
                        campaign.name,
                        new_line.product_id.display_name,
                        new_line.bom_id.code or "Default BoM",
                        new_line.product_demand_qty,
                    )
                    campaign._sync_date_planned_start()
