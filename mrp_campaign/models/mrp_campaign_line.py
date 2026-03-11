from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Many2many
from odoo.tools import float_is_zero

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
from odoo.addons.mrp.models.mrp_production import MrpProduction
from odoo.addons.product.models.product_product import ProductProduct


class CampaignLine(models.Model):
    _name = "mrp.campaign.line"
    _description = "Campaign breakdown line"

    campaign_id = fields.Many2one("mrp.campaign", ondelete="cascade")
    production_ids = fields.One2many("mrp.production", "campaign_line_id")
    demand_ids = fields.One2many("mrp.campaign.demand", "campaign_line_id")

    product_id = fields.Many2one("product.product")
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id")
    product_template_variant_value_ids = fields.Many2many(
        related="product_id.product_template_variant_value_ids"
    )

    qty = fields.Float(
        compute="_compute_qty",
        recursive=True,
        store=True,
        help="Total quantity planned",
    )
    pre_buffer_qty = fields.Float(
        compute="_compute_qty",
        recursive=True,
        store=True,
        help="Quantity before buffer was applied",
    )
    fulfilled_qty = fields.Float(
        compute="_compute_fulfilled_qty", store=True, help="Quantity already produced"
    )
    producing_qty = fields.Float(
        compute="_compute_production_qtys",
        store=True,
        help="Total quantity (planned, commited and complete) by MOs",
    )
    committed_qty = fields.Float(
        compute="_compute_production_qtys",
        store=True,
        help="Quantity committed by MOs (in progress and done)",
    )
    bom_id = fields.Many2one("mrp.bom")

    is_batch_produced = fields.Boolean(compute="_compute_is_batch_produced", store=True)
    batch_size = fields.Float(compute="_compute_batch_size", store=True)

    use_buffer = fields.Boolean(compute="_compute_use_buffer", store=True)
    buffer_percent = fields.Float(related="campaign_id.buffer_percent")

    is_out_of_sync = fields.Boolean(compute="_compute_is_out_of_sync")

    downstream_line_id = fields.Many2one("mrp.campaign.line", ondelete="cascade")
    downstream_product_id = fields.Many2one(
        "product.product", compute="_compute_downstream_product"
    )

    upstream_line_ids = fields.One2many("mrp.campaign.line", "downstream_line_id")
    sequence = fields.Integer(default=0)

    productions_created = fields.Boolean()

    @api.depends("qty", "producing_qty")
    def _compute_is_out_of_sync(self) -> None:
        for rec in self:
            rec.is_out_of_sync = not float_is_zero(
                rec.qty - rec.producing_qty,
                precision_rounding=rec.product_id.uom_id.rounding,
            )

    @api.depends("product_id")
    def _compute_is_batch_produced(self) -> None:
        for rec in self:
            rec.is_batch_produced = rec.product_tmpl_id.mrp_max_batch_size != 0

    @api.depends(
        "product_id", "campaign_id.override_batch_size", "campaign_id.batch_size"
    )
    def _compute_batch_size(self) -> None:
        for rec in self:
            rec.batch_size = (
                rec.campaign_id.batch_size
                if rec.campaign_id.override_batch_size
                else rec.product_tmpl_id.mrp_max_batch_size
            )

    @api.depends("is_batch_produced")
    def _compute_use_buffer(self) -> None:
        for rec in self:
            rec.use_buffer = rec.is_batch_produced

    @api.depends("bom_id")
    def _compute_downstream_product(self) -> None:
        for rec in self:
            rec.downstream_product_id = rec._get_downstream_product()

    @api.depends("production_ids", "production_ids.qty_produced")
    def _compute_fulfilled_qty(self) -> None:
        for rec in self:
            rec.fulfilled_qty = sum(rec.production_ids.mapped("qty_produced"))

    @api.depends(
        "upstream_line_ids",
        "upstream_line_ids.qty",
        "demand_ids",
        "demand_ids.target_qty",
    )
    def _compute_qty(self) -> None:
        for rec in self:
            buffer = (1 + rec.buffer_percent) if rec.is_batch_produced else 1
            if rec.upstream_line_ids:
                quantities = [
                    line.qty * line.bom_id.get_factor_to_product(rec.product_id)
                    for line in rec.upstream_line_ids
                ]
                rec.pre_buffer_qty = sum(quantities)
                rec.qty = rec.pre_buffer_qty * buffer

            elif rec.demand_ids:
                rec.pre_buffer_qty = sum(rec.demand_ids.mapped("target_qty"))
                rec.qty = rec.pre_buffer_qty * buffer

            else:
                rec.pre_buffer_qty = 0
                rec.qty = 0

    @api.depends("production_ids", "production_ids.product_qty", "production_ids.state")
    def _compute_production_qtys(self) -> None:
        for rec in self:
            rec.producing_qty = sum(
                rec.production_ids.filtered_domain(
                    [
                        (
                            "state",
                            "!=",
                            "cancel",
                        )
                    ]
                ).mapped("product_qty")
            )
            committed_qty = sum(
                rec.production_ids.filtered_domain(
                    [("state", "not in", ["draft", "cancel", "confirmed"])]
                ).mapped("product_qty")
            )
            rec.committed_qty = committed_qty / (
                (1 + rec.buffer_percent) if rec.is_batch_produced else 1
            )

    def write(self, vals) -> bool:
        res = super().write(vals)

        if self.env.context.get("campaign_skip_mo_adjustment"):
            return res

        # After the math is written to the DB, sync the physical MOs
        if "qty" in vals or self.env.is_to_compute("qty", self):
            for rec in self.filtered("productions_created"):
                rec._adjust_mos(rec.qty)

        return res

    def _get_downstream_product(self) -> ProductProduct:
        self.ensure_one()
        if not self.bom_id:
            return self.env["product.product"]
        if self.product_tmpl_id.is_campaign_anchor:
            return self.env["product.product"]

        if self.bom_id.type == "phantom":
            raise ValidationError(
                _("Kits (Phantom BoMs) are not supported in manufacturing campaigns.")
            )

        anchors: ProductProduct = (
            self.bom_id.bom_line_ids.filtered(self.is_valid_bom_line_for_product)
            .mapped("product_id")
            .filtered("anchor_product_id")
        )
        if len(anchors) != 1:
            raise ValidationError(
                _(
                    "Could not resolve downstream product "
                    "for %(product)s with BoM %(bom)s"
                    % {
                        "product": self.product_id.display_name,
                        "bom": self.bom_id.code,
                    },
                )
            )
        return anchors

    def _construct_downstream_tree_line(self, depth=0) -> None:
        self.ensure_one()
        self.sequence = depth

        if not self.bom_id:
            return

        # Anchors are the last level of the campaign tree.
        # We do not manage the production of their components here.
        if self.product_tmpl_id.is_campaign_anchor:
            return

        for bom_line in self.bom_id.bom_line_ids.filtered(
            lambda x: self.is_valid_bom_line_for_product(x) and x.product_id.bom_ids
        ):
            downstream_product = bom_line.product_id
            downstream_bom = self.env["mrp.bom"]._bom_find(
                products=downstream_product, company_id=self.campaign_id.company_id.id
            )[downstream_product]

            if not downstream_bom:
                continue

            if downstream_bom.type == "phantom":
                raise ValidationError(
                    _(
                        "Kits (Phantom BoMs) are not supported in "
                        "manufacturing campaigns. "
                        "Found kit: %s",
                        downstream_bom.display_name,
                    )
                )

            existing_downstream_line = self.campaign_id.line_ids.filtered(
                lambda line, ds_product=downstream_product, ds_bom=downstream_bom: (
                    line.product_id == ds_product and line.bom_id == ds_bom
                )
            )
            if existing_downstream_line:
                self.downstream_line_id = existing_downstream_line
                existing_downstream_line._construct_downstream_tree_line(depth + 1)

            else:
                new_downstream_line = self.env["mrp.campaign.line"].create(
                    {
                        "campaign_id": self.campaign_id.id,
                        "product_id": downstream_product.id,
                        "bom_id": downstream_bom.id,
                        "sequence": depth + 1,
                    }
                )
                self.downstream_line_id = new_downstream_line
                new_downstream_line._construct_downstream_tree_line(depth + 1)

    def make_production_order(self) -> MrpProduction:
        values = []
        for rec in self:
            values += rec._make_production_order()
        mos: MrpProduction = self.env["mrp.production"].create(values)
        self.productions_created = True
        return mos

    def _make_production_order(self) -> list[dict]:
        self.ensure_one()
        values = []
        if self.is_batch_produced and self.batch_size > 0:
            remaining_qty = self.qty

            while not float_is_zero(remaining_qty, self.product_id.uom_id.rounding):
                qty_to_produce = min(remaining_qty, self.batch_size)
                remaining_qty -= qty_to_produce

                values.append(
                    {
                        "product_id": self.product_id.id,
                        "bom_id": self.bom_id.id,
                        "product_qty": qty_to_produce,
                        "campaign_line_id": self.id,
                        "created_by_campaign": True,
                        "date_start": self.campaign_id.date_planned_start,
                    }
                )
        else:
            values.append(
                {
                    "product_id": self.product_id.id,
                    "bom_id": self.bom_id.id,
                    "product_qty": self.qty,
                    "campaign_line_id": self.id,
                    "created_by_campaign": True,
                    "date_start": self.campaign_id.date_planned_start,
                }
            )

        return values

    def is_valid_bom_line_for_product(self, bom_line: MrpBomLine) -> bool:
        self.ensure_one()
        if self.product_id.product_tmpl_id != bom_line.bom_id.product_tmpl_id:
            return False
        bom_line_variant_ids: Many2many = (
            bom_line.bom_product_template_attribute_value_ids
        )

        if not bom_line_variant_ids or not self.product_template_variant_value_ids:
            return True

        union = self.product_template_variant_value_ids & bom_line_variant_ids
        return union

    def _get_anchor_factor(self) -> float:
        self.ensure_one()

        if not self.downstream_product_id:
            return 1
        else:
            own_factor = self._get_downstream_factor()
            downstream_factor = self.downstream_line_id._get_anchor_factor()
            return own_factor * downstream_factor

    def _get_downstream_factor(self) -> float:
        self.ensure_one()
        return (
            self.bom_id.get_factor_to_product(self.downstream_product_id)
            if self.downstream_product_id
            else 1
        )

    def _adjust_mos(self, new_quantity: float) -> None:
        self.ensure_one()

        rounding_precision = self.product_id.uom_id.rounding

        # Separate MOs into those that can be adjusted/deleted and
        # those that are fixed (e.g., done or cancelled)
        # MOs in 'draft', 'confirmed' states are considered adjustable.
        active_mos = self.production_ids.filtered_domain(
            [("state", "not in", ["cancel"])]
        )
        adjustable_mos = active_mos.filtered(
            lambda mo: mo.state in ["draft", "confirmed"]
        )
        fixed_mos = active_mos - adjustable_mos
        fixed_qty_produced = sum(fixed_mos.mapped("product_qty"))

        required_from_adjustable_mos = new_quantity - fixed_qty_produced

        if required_from_adjustable_mos < 0:
            raise ValidationError(
                _(
                    "Cannot adjust to a quantity less than what has already "
                    "been produced by existing Manufacturing Orders "
                    "that are in 'Done' or 'Cancelled' states. "
                    "(Requested: %(new_quantity)s, "
                    "Fixed Produced: %(fixed_qty_produced)s)"
                )
                % {
                    "new_quantity": new_quantity,
                    "fixed_qty_produced": fixed_qty_produced,
                }
            )

        if float_is_zero(new_quantity, precision_rounding=rounding_precision):
            adjustable_mos.unlink()
            return

        if self.is_batch_produced and self.batch_size > 0:
            self._adjust_batch_mos(adjustable_mos, required_from_adjustable_mos)

        else:  # Not batch produced or infinite batch size
            if not float_is_zero(
                required_from_adjustable_mos,
                precision_rounding=rounding_precision,
            ):
                if len(adjustable_mos) > 1:
                    raise ValidationError(
                        _(
                            "Non-batch produced line should only "
                            "have one Manufacturing Order."
                        )
                    )
                elif len(adjustable_mos) == 1:
                    mo = adjustable_mos[0]
                    self.env["change.production.qty"].create(
                        {
                            "mo_id": mo.id,
                            "product_qty": required_from_adjustable_mos,
                        }
                    ).change_prod_qty()
                else:  # len(adjustable_mos) == 0, create a new one
                    self.env["mrp.production"].create(
                        {
                            "product_id": self.product_id.id,
                            "bom_id": self.bom_id.id,
                            "product_qty": required_from_adjustable_mos,
                            "campaign_line_id": self.id,
                            "created_by_campaign": True,
                        }
                    )
            else:
                adjustable_mos.unlink()

    def _adjust_batch_mos(
        self, adjustable_mos: MrpProduction, required_from_adjustable_mos: float
    ) -> None:
        self.ensure_one()
        rounding_precision = self.product_id.uom_id.rounding

        # 1. Determine the target structure of MOs required
        target_mo_quantities = []
        n_full_batches = int(required_from_adjustable_mos / self.batch_size)
        remaining_qty_for_partial = required_from_adjustable_mos % self.batch_size

        for _n in range(n_full_batches):
            target_mo_quantities.append(self.batch_size)
        if not float_is_zero(
            remaining_qty_for_partial,
            precision_rounding=rounding_precision,
        ):
            target_mo_quantities.append(remaining_qty_for_partial)

        unassigned_targets = list(target_mo_quantities)

        # 2. Match existing MOs to target quantities
        #  (Exact matches first, then closest fit)
        mo_updates = []
        assigned_adjustable_mos = self.env["mrp.production"]

        # Sort MOs to process them consistently
        for current_mo in adjustable_mos.sorted("product_qty", reverse=True):
            best_match_idx = -1
            min_diff = float("inf")

            for idx, target_qty in enumerate(unassigned_targets):
                if target_qty is None:
                    continue

                diff = abs(current_mo.product_qty - target_qty)
                if diff < min_diff:
                    min_diff = diff
                    best_match_idx = idx

                # Optimization: take exact match immediately
                if float_is_zero(diff, precision_rounding=rounding_precision):
                    break

            if best_match_idx != -1:
                matched_target_qty = unassigned_targets[best_match_idx]
                if not float_is_zero(
                    current_mo.product_qty - matched_target_qty,
                    precision_rounding=rounding_precision,
                ):
                    mo_updates.append((current_mo, matched_target_qty))

                unassigned_targets[best_match_idx] = None
                assigned_adjustable_mos |= current_mo

        # 3. Identify MOs to unlink and new values to create
        mo_unlinks = adjustable_mos - assigned_adjustable_mos
        mo_creation_values = [
            {
                "product_id": self.product_id.id,
                "bom_id": self.bom_id.id,
                "product_qty": target_qty,
                "campaign_line_id": self.id,
                "created_by_campaign": True,
            }
            for target_qty in unassigned_targets
            if target_qty is not None
        ]

        # 4. Execute database operations
        if mo_unlinks:
            mo_unlinks.unlink()

        for mo_record, new_qty in mo_updates:
            self.env["change.production.qty"].create(
                {"mo_id": mo_record.id, "product_qty": new_qty}
            ).change_prod_qty()

        if mo_creation_values:
            self.env["mrp.production"].create(mo_creation_values)

    def action_sync_line(self) -> None:
        self.ensure_one()
        self._adjust_mos(self.qty)
