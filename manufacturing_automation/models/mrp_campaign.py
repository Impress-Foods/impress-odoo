import colorsys
import logging
import random

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.stock.models.stock_rule import StockRule

from .procurement import Procurement

_logger = logging.getLogger(__name__)


class MrpCampaign(models.Model):
    _name = "mrp.campaign"
    _description = "Manufacturing Campaign"
    _order = "date_start desc,sequence desc"
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

    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)

    product_id = fields.Many2one(
        "product.product",
        string="Intermediate Product",
        required=True,
        domain="[('product_tmpl_id.is_campaign_manufactured', '=', True)]",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    demand_move_ids = fields.Many2many(
        "stock.move",
        string="Demand Moves",
        help="The individual lines from Consumer MOs requiring this product.",
    )

    provider_mo_ids = fields.One2many(
        "mrp.production",
        "campaign_id",
        string="Provider MOs",
        help="The production orders (tanks) created to satisfy this campaign.",
    )

    consumer_mo_ids = fields.Many2many(
        "mrp.production",
        string="Consumer MOs",
        compute="_compute_consumer_mo_ids",
        store=False,
        help="Finished product MOs that triggered the demand moves.",
    )
    provider_mo_count = fields.Integer(compute="_compute_mo_counts")
    consumer_mo_count = fields.Integer(compute="_compute_mo_counts")

    total_demand_qty = fields.Float(string="Total Demand", compute="_compute_totals")
    planned_supply_qty = fields.Float(
        string="Planned Supply", compute="_compute_totals"
    )
    percent_fulfilled = fields.Float(compute="_compute_percent")
    campaign_balance = fields.Float(
        string="Balance",
        compute="_compute_totals",
        help="Difference between Supply and Demand. Should be >= 0.",
    )

    lot_id = fields.Many2one(comodel_name="stock.lot")
    override_batch_size = fields.Boolean()
    batch_size = fields.Float()

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

    @api.depends("consumer_mo_ids", "provider_mo_ids", "demand_move_ids")
    def _compute_mo_counts(self):
        for rec in self:
            rec.provider_mo_count = len(rec.provider_mo_ids)
            rec.consumer_mo_count = len(rec.consumer_mo_ids)
            if rec.provider_mo_count == 0:
                rec._action_draft()

    def _action_draft(self):
        for rec in self:
            rec.state = "draft"

    @api.depends(
        "demand_move_ids",
        "demand_move_ids.state",
        "demand_move_ids.product_uom_qty",
        "provider_mo_ids.product_qty",
        "provider_mo_ids.state",
    )
    def _compute_totals(self):
        for rec in self:
            active_demand_moves = rec.demand_move_ids.filtered(
                lambda m: m.exists() and m.state != "cancel"
            )

            rec.total_demand_qty = sum(active_demand_moves.mapped("product_uom_qty"))

            active_provider_mos = rec.provider_mo_ids.filtered(
                lambda mo: mo.state != "cancel"
            )
            rec.planned_supply_qty = sum(active_provider_mos.mapped("product_qty"))

            rec.campaign_balance = rec.planned_supply_qty - rec.total_demand_qty

    @api.depends("planned_supply_qty", "total_demand_qty")
    def _compute_percent(self):
        for rec in self:
            rec.percent_fulfilled = (
                (rec.planned_supply_qty / rec.total_demand_qty) * 100
                if rec.total_demand_qty > 0
                else 100.0
            )

    @api.depends("demand_move_ids")
    def _compute_consumer_mo_ids(self):
        for rec in self:
            rec.consumer_mo_ids = rec.demand_move_ids.mapped(
                "raw_material_production_id"
            )

    def _sync_campaign_lots(self, reference_lot):
        """
        Triggered when any MO in the campaign gets a lot assigned.
        Propagates the same Lot to providers and the same Name to consumers.
        """
        self.ensure_one()
        lot_name = reference_lot.name
        self.lot_id = reference_lot
        company_id = reference_lot.company_id.id

        providers_to_update = self.provider_mo_ids.filtered(
            lambda m: m.lot_producing_id != reference_lot
        )
        if providers_to_update:
            providers_to_update.with_context(skip_campaign_sync=True).write(
                {"lot_producing_id": reference_lot.id}
            )

        lot_cache = {}

        for mo in self.consumer_mo_ids:
            target_product = mo.product_id

            if target_product not in lot_cache:
                existing_lot = self.env["stock.lot"].search(
                    [
                        ("name", "=", lot_name),
                        ("product_id", "=", target_product.id),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )

                if existing_lot:
                    lot_cache[target_product] = existing_lot
                else:
                    lot_cache[target_product] = self.env["stock.lot"].create(
                        {
                            "name": lot_name,
                            "product_id": target_product.id,
                            "company_id": company_id,
                        }
                    )

            if mo.lot_producing_id != lot_cache[target_product]:
                mo.with_context(skip_campaign_sync=True).write(
                    {"lot_producing_id": lot_cache[target_product].id}
                )

    def action_confirm(self):
        """Logic to split total demand into batch-sized Provider MOs"""
        for rec in self:
            if not rec.demand_move_ids:
                raise UserError(_("No demand moves selected."))

            batch_size = rec.product_id.product_tmpl_id.mrp_max_batch_size

            if batch_size <= 0:
                raise UserError(
                    _("Please define a Max Batch Size on the product template.")
                )

            if rec.override_batch_size:
                if rec.batch_size <= 0:
                    raise UserError(_("Please define an Override batch size"))
                batch_size = rec.batch_size

            remaining = rec.total_demand_qty
            while remaining > 0:
                qty = min(batch_size, remaining)
                mo = self.env["mrp.production"].create(
                    {
                        "product_id": rec.product_id.id,
                        "product_uom_id": rec.product_id.uom_id.id,
                        "product_qty": qty,
                        "campaign_id": rec.id,
                        "associated_campaign_id": rec.id,
                        "origin": rec.name,
                        "bom_id": rec.product_id.bom_ids[0].id,
                    }
                )
                mo.action_confirm()
                mo.action_assign_all()
                remaining -= qty

            rec.state = "confirmed"

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_check_availability(self):
        """Helper for the planner: Try to reserve stock for all consumers at once."""
        self.demand_move_ids._action_assign()

    @api.model
    def _get_or_create_active(self, product, company):
        """
        Finds a Draft campaign for the product/company that is 'open' for demand.
        If none exists, creates a new planning bucket.
        """
        today = fields.Date.today()
        bucket_size = product.product_tmpl_id.campaign_bucket_size
        bucket_type = product.product_tmpl_id.campaign_bucket_type

        start_date = today
        end_date = today

        if bucket_type == "day":
            start_date = today
            end_date = today + relativedelta(days=bucket_size - 1)
        elif bucket_type == "week":
            # Assuming week starts on Monday (weekday() returns 0 for Monday)
            start_date = today - relativedelta(days=today.weekday())
            end_date = (
                start_date + relativedelta(weeks=bucket_size) - relativedelta(days=1)
            )
        elif bucket_type == "month":
            start_date = today.replace(day=1)
            end_date = (
                start_date + relativedelta(months=bucket_size) - relativedelta(days=1)
            )

        campaign = self.search(
            [
                ("product_id", "=", product.id),
                ("company_id", "=", company.id),
                ("state", "=", "draft"),
                ("date_start", "<=", start_date),
                ("date_end", ">=", end_date),
            ],
            limit=1,
        )

        if not campaign:
            campaign = self.create(
                {
                    "name": self._get_name_seq(),
                    "product_id": product.id,
                    "company_id": company.id,
                    "date_start": start_date,
                    "date_end": end_date,
                    "state": "draft",
                }
            )

        return campaign

    @api.model
    def _collect_procurements(self, procurements: list[tuple[Procurement, StockRule]]):
        """
        Main entry point from stock.rule interception.
        Takes a list of procurement objects and routes their moves to campaigns.
        """
        for procurement, _rule in procurements:
            demand_moves = procurement.values.get("move_dest_ids")
            if not demand_moves:
                continue

            campaign = self._get_or_create_active(
                product=procurement.product_id, company=procurement.company_id
            )
            campaign.demand_move_ids |= demand_moves

            demand_moves.write(
                {
                    "demanded_by_campaign_id": campaign.id,
                    "origin": f"{demand_moves[0].origin or ''} - {campaign.name}".strip(
                        "-"
                    ),
                }
            )

    def action_view_provider_mos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Provider Manufacturing Orders"),
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("campaign_id", "=", self.id)],
            "context": {"default_campaign_id": self.id},
        }

    def action_view_consumer_mos(self):
        self.ensure_one()
        consumer_ids = self.consumer_mo_ids.ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Consumer Manufacturing Orders"),
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("id", "in", consumer_ids)],
            "context": {"create": False},
        }
