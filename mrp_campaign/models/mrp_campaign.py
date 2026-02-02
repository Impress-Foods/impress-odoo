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
            ("review", "In Review"),
            ("confirmed", "Confirmed"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
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
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    lot_name = fields.Char()
    override_batch_size = fields.Boolean()
    batch_size = fields.Float()

    line_ids = fields.One2many(
        "mrp.campaign.line", "campaign_id", string="Demand Lines"
    )

    provider_move_ids = fields.One2many(
        "stock.move",
        "campaign_id",
        string="Provider Moves",
        help="Stock moves created to produce the batched product for this campaign.",
    )

    bulk_created = fields.Boolean()
    end_created = fields.Boolean()

    production_ids = fields.One2many("mrp.production", "campaign_id")
    production_count = fields.Integer(compute="_compute_production_count")

    @api.depends("production_ids")
    def _compute_production_count(self):
        for rec in self:
            rec.production_count = len(rec.production_ids)

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

    def action_confirm_end(self):
        for campaign in self:
            if not campaign.end_created:
                if not campaign.line_ids:
                    raise UserError(
                        _(
                            "Cannot confirm campaign %s without any demand.",
                            campaign.name,
                        )
                    )

                # Part 2: Create MOs for the finished goods on each line
                mos = self.env["mrp.production"]
                for line in campaign.line_ids:
                    mos += line._create_finished_product_mo(confirm=False)

                # MOs are created in draft, awaiting user adjustment.
                # Part 3: Update campaign state
                campaign.write({"state": "review", "end_created": True})
        return True

    def action_confirm_bulk(self):
        for campaign in self:
            if not campaign.bulk_created:
                # 1. Confirm 'end' MOs that are still in draft state
                end_mos_to_confirm = campaign.production_ids.filtered(
                    lambda mo: mo.state == "draft"
                )
                if end_mos_to_confirm:
                    end_mos_to_confirm.with_context(
                        ignore_campaign_procurement=True
                    ).action_confirm()

                anchor_product = campaign.product_id
                # 2. Calculate total anchor demand from confirmed 'end' MOs' raw moves
                # The campaign.production_ids will now contain confirmed MOs
                total_anchor_qty_needed = sum(
                    campaign.line_ids.mapped("anchor_product_qty")
                )

                if total_anchor_qty_needed > 0:
                    # Find BoM for anchor product, needed to create MO
                    anchor_bom = self.env["mrp.bom"]._bom_find(products=anchor_product)[
                        anchor_product
                    ]
                    if not anchor_bom:
                        raise UserError(
                            _(
                                "No Bill of Materials found for the anchor product %s.",
                                anchor_product.display_name,
                            )
                        )

                    batch_size = (
                        campaign.batch_size
                        if campaign.override_batch_size and campaign.batch_size > 0
                        else campaign.product_id.mrp_max_batch_size
                    )
                    remaining_qty = total_anchor_qty_needed
                    mos_to_create = []
                    while remaining_qty > 1e-6:
                        qty_to_produce = min(batch_size, remaining_qty)
                        remaining_qty -= qty_to_produce

                        mos_to_create.append(
                            {
                                "product_id": anchor_product.id,
                                "product_uom_id": anchor_product.uom_id.id,
                                "product_qty": qty_to_produce,
                                "campaign_id": campaign.id,
                                "origin": campaign.name,
                                "date_start": datetime.combine(
                                    campaign.date_planned_start, time(5, 0)
                                ),
                                "date_deadline": datetime.combine(
                                    campaign.date_planned_start, time(12, 0)
                                ),
                                "bom_id": anchor_bom.id,
                                "created_by_campaign": True,
                            }
                        )

                    anchor_mos = self.env["mrp.production"]
                    if mos_to_create:
                        anchor_mos = self.env["mrp.production"].create(mos_to_create)
                        # 3. Create and confirm 'bulk' MOs
                        anchor_mos.action_confirm()

                    # 4. Link bulk MO finished moves to end MO raw moves
                    if anchor_mos and total_anchor_qty_needed > 0:
                        provider_moves = anchor_mos.mapped("move_finished_ids")
                        consumer_moves = campaign.production_ids.mapped(
                            "move_raw_ids"
                        ).filtered(
                            lambda move, anchor_product=anchor_product: move.product_id
                            == anchor_product
                        )

                        if provider_moves and consumer_moves:
                            provider_moves.write(
                                {"move_dest_ids": [(6, 0, consumer_moves.ids)]}
                            )

                # 5. Update campaign state
                campaign.write({"state": "confirmed", "bulk_created": True})
        return True

    def action_reset(self):
        """
        Resets a confirmed campaign back to draft, deleting any manufacturing
        orders and stock moves that were created by the confirmation process.
        """
        for campaign in self.filtered(
            lambda c: c.state
            in [
                "review",
                "confirmed",
            ]
        ):
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

            # The moves should have been cancelled by the MO cancellation,
            # but we ensure they are unlinked to complete the reset.
            provider_moves = self.env["stock.move"].search(
                [("campaign_id", "=", campaign.id)]
            )
            if provider_moves:
                provider_moves.unlink()

            campaign.write(
                {"state": "draft", "bulk_created": False, "end_created": False}
            )

        return True

    def action_view_mos(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "tree,form",
            "target": "current",
        }

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
            anchor_product = procurement.product_id._get_anchor_product()
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
                campaign_line = campaign.line_ids.filtered(
                    lambda line, p=procurement, b=bom: line.product_id == p.product_id
                    and line.bom_id == b
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
                    new_line = self.env["mrp.campaign.line"].create(
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


class MrpCampaignLine(models.Model):
    _name = "mrp.campaign.line"
    _description = "Manufacturing Campaign Line"

    campaign_id = fields.Many2one(
        "mrp.campaign", string="Campaign", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id"
    )
    product_demand_qty = fields.Float(
        "Demand Quantity", compute="_compute_product_demand_qty", store=True
    )
    anchor_product_qty = fields.Float(
        string="Required Component Qty",
        compute="_compute_anchor_product_qty",
        store=True,
        help=(
            "The quantity of the intermediate product (anchor) required "
            "to fulfill the demand for this line."
        ),
    )
    move_dest_ids = fields.Many2many(
        "stock.move",
        string="Destination Moves",
        help="Moves that this production will fulfill.",
    )
    product_uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )
    component_uom_id = fields.Many2one(
        related="campaign_id.product_id.product_tmpl_id.uom_id"
    )

    production_id = fields.Many2one("mrp.production", ondelete="set null")

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Bill of Materials",
        help="The specific BoM to be used for manufacturing the product on this line.",
    )

    @api.depends("move_dest_ids", "production_id.product_qty")
    def _compute_product_demand_qty(self):
        for rec in self:
            if rec.production_id:
                rec.product_demand_qty = rec.production_id.product_qty
            else:
                rec.product_demand_qty = sum(
                    rec.move_dest_ids.mapped("product_uom_qty")
                )

    @api.depends("product_demand_qty", "bom_id", "campaign_id.product_id")
    def _compute_anchor_product_qty(self):
        """
        Calculates the required quantity of the campaign's anchor product
        for this specific campaign line.
        """
        for line in self:
            if not line.bom_id or not line.campaign_id.product_id:
                line.anchor_product_qty = 0.0
                continue

            anchor_product = line.campaign_id.product_id
            _boms, bom_lines = line.bom_id.explode(
                line.product_id, line.product_demand_qty
            )

            needed_qty = 0.0
            for bom_line, line_data in bom_lines:
                if bom_line.product_id == anchor_product:
                    needed_qty += line_data["qty"]
            line.anchor_product_qty = needed_qty

    def _create_finished_product_mo(self, confirm=True):
        """
        Creates a manufacturing order for the finished product of this line
        and links it to the campaign and original demand moves.
        """
        self.ensure_one()
        if not self.bom_id:
            raise UserError(
                _(
                    (
                        "Cannot create Manufacturing Order for line"
                        "with product %s because it is missing a Bill of Materials."
                    ),
                    self.product_id.display_name,
                )
            )

        mo = self.env["mrp.production"].create(
            {
                "product_id": self.product_id.id,
                "bom_id": self.bom_id.id,
                "product_qty": self.product_demand_qty,
                "product_uom_id": self.product_uom_id.id,
                "origin": self.campaign_id.name,
                "date_start": datetime.combine(
                    self.campaign_id.date_planned_start, time(13, 0)
                ),
                "date_deadline": datetime.combine(
                    self.campaign_id.date_planned_start, time(23, 0)
                ),
                "campaign_id": self.campaign_id.id,  # Link as a consumer
                "created_by_campaign": True,
            }
        )

        if self.move_dest_ids:
            # Link the original SO moves to this consolidated MO for traceability
            self.move_dest_ids.write({"created_production_id": mo.id})

        if confirm:
            mo.action_confirm()
        self.production_id = mo

        if mo.move_finished_ids:
            mo.move_finished_ids.write(
                {"move_dest_ids": [(6, 0, self.move_dest_ids.ids)]}
            )

        return mo
