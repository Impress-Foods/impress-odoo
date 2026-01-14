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
    date_planned_start = fields.Datetime(
        string="Scheduled Date", required=True, default=fields.Datetime.now
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
            rec.production_count = len(self.production_ids)

    @api.depends(
        "bucket_start_date",
        "product_id.campaign_bucket_type",
        "product_id.campaign_bucket_size",
    )
    def _compute_bucket_end_date(self) -> None:
        for rec in self:
            bucket_period: Literal["day", "week", "month", "year"] = (
                rec.product_id.campaign_bucket_type
            )
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

            rec.bucket_end_date = rec.bucket_start_date + delta

    def action_confirm_end(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Cannot confirm a campaign without any demand lines."))

        # Part 2: Create MOs for the finished goods on each line
        mos = self.env["mrp.production"]
        for line in self.line_ids:
            mos += line._create_finished_product_mo(confirm=False)

        mos.action_confirm()
        # Part 3: Update campaign state
        self.write({"state": "confirmed"})
        self.end_created = True
        return True

    def action_confirm_bulk(self):
        self.ensure_one()
        # Part 1: Calculate total anchor demand and create batched MOs for it
        anchor_product = self.product_id
        total_anchor_qty_needed = sum(
            self.line_ids.mapped(
                lambda line: line._get_anchor_product_qty(anchor_product)
            )
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
                self.batch_size
                if self.override_batch_size and self.batch_size > 0
                else self.product_id.mrp_max_batch_size
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
                        "campaign_id": self.id,
                        "origin": self.name,
                        "date_start": self.date_planned_start,
                        "bom_id": anchor_bom.id,
                    }
                )

            if mos_to_create:
                anchor_mos = self.env["mrp.production"].create(mos_to_create)
                anchor_mos.action_confirm()

                # # Link the resulting provider moves to the network
                # provider_moves = anchor_mos.mapped("move_finished_ids")
                # original_demand_moves = self.line_ids.mapped("move_dest_ids")
                # provider_moves.write(
                #     {
                #         "campaign_id": self.id,
                #         "move_orig_ids": [(6, 0, original_demand_moves.ids)],
                #     }
                # )
            self.bulk_created = True

    def action_reset(self):
        """
        Resets a confirmed campaign back to draft, deleting any manufacturing
        orders and stock moves that were created by the confirmation process.
        """
        for campaign in self.filtered(lambda c: c.state == "confirmed"):
            # Find and cancel any manufacturing orders created for this campaign
            productions = self.env["mrp.production"].search(
                [("campaign_id", "=", campaign.id)]
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

            campaign.write({"state": "draft"})

            campaign.line_ids.filtered(
                lambda line, campaign=campaign: line.product_id == campaign.product_id
            ).unlink()

            campaign.bulk_created = False
            campaign.end_created = False
        return True

    def action_view_mos(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "domain": [("id", "in", self.production_ids.ids)],
            "view_mode": "tree,form",
            "target": "current",
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
    def _get_or_create_campaign_for_anchor(self, anchor_product, company):
        """
        Finds or creates a Draft campaign for the given anchor product and company.
        """
        campaign = self.search(
            [
                ("product_id", "=", anchor_product.id),
                ("company_id", "=", company.id),
                ("state", "=", "draft"),
            ],
            limit=1,
            order="date_planned_start asc",  # Get the oldest one
        )

        if not campaign:
            campaign = self.create(
                {
                    "product_id": anchor_product.id,
                    "company_id": company.id,
                    "bucket_start_date": fields.datetime.now().date(),
                }
            )
            _logger.info(
                "Created new campaign %s for anchor %s.",
                campaign.name,
                anchor_product.display_name,
            )
        else:
            _logger.info(
                "Found existing campaign %s for anchor %s.",
                campaign.name,
                anchor_product.display_name,
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

        for procurement, _rule in procurements:
            # 1. Recursive Anchor Search
            anchor_product = procurement.product_id._get_anchor_product()

            if not anchor_product:
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

            # 2. Determine the BoM
            bom = procurement.values.get("bom_id")
            if not bom:
                bom = self.env["mrp.bom"]._bom_find(products=procurement.product_id)[
                    procurement.product_id
                ]

            # 3. Search/Create Campaign for that Anchor
            campaign = self._get_or_create_campaign_for_anchor(
                anchor_product=anchor_product, company=procurement.company_id
            )

            # 4. Update Reservoir (mrp.campaign.line), now unique by product AND bom
            campaign_line = campaign.line_ids.filtered(
                lambda line, p=procurement, b=bom: line.product_id == p.product_id
                and line.bom_id == b
            )

            if campaign_line:
                # Aggregate quantity on the existing line.
                campaign_line.product_uom_qty += procurement.product_qty
                # Add new demand moves to the existing ones.
                campaign_line.move_dest_ids |= demand_moves
                _logger.info(
                    "Updated line in campaign %s: %s (%s) +%f units.",
                    campaign.name,
                    campaign_line.product_id.display_name,
                    campaign_line.bom_id.code or "Default BoM",
                    procurement.product_qty,
                )

            else:
                # Create a new line for this product/bom combination.
                self.env["mrp.campaign.line"].create(
                    {
                        "campaign_id": campaign.id,
                        "product_id": procurement.product_id.id,
                        "bom_id": bom.id if bom else False,
                        "product_uom_qty": procurement.product_qty,
                        "move_dest_ids": [(6, 0, demand_moves.ids)],
                    }
                )
                _logger.info(
                    "Created new line in campaign %s: %s (%s), %f units.",
                    campaign.name,
                    procurement.product_id.display_name,
                    bom.code or "Default BoM",
                    procurement.product_qty,
                )


class MrpCampaignLine(models.Model):
    _name = "mrp.campaign.line"
    _description = "Manufacturing Campaign Line"

    campaign_id = fields.Many2one(
        "mrp.campaign", string="Campaign", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_uom_qty = fields.Float(
        "Quantity", default=1.0, compute="_compute_product_uom_qty"
    )
    move_dest_ids = fields.Many2many(
        "stock.move",
        string="Destination Moves",
        help="Moves that this production will fulfill.",
    )
    product_uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )

    production_id = fields.Many2one("mrp.production")

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Bill of Materials",
        help="The specific BoM to be used for manufacturing the product on this line.",
    )

    @api.depends("move_dest_ids")
    def _compute_product_uom_qty(self):
        for rec in self:
            rec.product_uom_qty = sum(rec.move_dest_ids.mapped("product_uom_qty"))

    def _get_anchor_product_qty(self, anchor_product):
        """
        Calculates the required quantity of a given anchor_product
        for this specific campaign line.
        """
        self.ensure_one()
        if not self.bom_id:
            return 0.0

        _boms, bom_lines = self.bom_id.explode(self.product_id, self.product_uom_qty)

        needed_qty = 0.0
        for bom_line, line_data in bom_lines:
            if bom_line.product_id == anchor_product:
                needed_qty += line_data["qty"]
        return needed_qty

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
                "product_qty": self.product_uom_qty,
                "product_uom_id": self.product_uom_id.id,
                "origin": self.campaign_id.name,
                "date_start": datetime.combine(
                    self.campaign_id.date_planned_start, time.min
                ),
                "date_deadline": datetime.combine(
                    self.campaign_id.date_planned_start, time.max
                ),
                "campaign_id": self.campaign_id.id,  # Link as a consumer
            }
        )

        if confirm:
            mo.action_confirm()
        self.production_id = mo

        if mo.move_finished_ids:
            mo.move_finished_ids.write(
                {"move_dest_ids": [(6, 0, self.move_dest_ids.ids)]}
            )

        return mo
