import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Many2many
from odoo.tools import float_is_zero

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
from odoo.addons.mrp.models.mrp_production import MrpProduction
from odoo.addons.mrp.wizard.change_production_qty import ChangeProductionQty
from odoo.addons.product.models.product_product import ProductProduct

_logger = logging.getLogger(__name__)


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

    qty = fields.Float(compute="_compute_qty", recursive=True, store=True)
    fulfilled_qty = fields.Float(compute="_compute_fulfilled_qty", store=True)
    producing_qty = fields.Float(compute="_compute_producing_qty", store=True)
    bom_id = fields.Many2one("mrp.bom")

    is_batch_produced = fields.Boolean(compute="_compute_is_batch_produced", store=True)
    batch_size = fields.Float(compute="_compute_batch_size", store=True)

    use_buffer = fields.Boolean(compute="_compute_use_buffer", store=True)
    buffer_percent = fields.Float(related="campaign_id.buffer_percent")

    downstream_line_id = fields.Many2one("mrp.campaign.line", ondelete="cascade")
    downstream_product_id = fields.Many2one(
        "product.product", compute="_compute_downstream_product"
    )

    upstream_line_ids = fields.One2many("mrp.campaign.line", "downstream_line_id")
    sequence = fields.Integer(default=0)

    productions_created = fields.Boolean()

    @api.depends("product_id")
    def _compute_is_batch_produced(self):
        for rec in self:
            rec.is_batch_produced = rec.product_tmpl_id.mrp_max_batch_size != 0

    @api.depends(
        "product_id", "campaign_id.override_batch_size", "campaign_id.batch_size"
    )
    def _compute_batch_size(self):
        for rec in self:
            rec.batch_size = (
                rec.campaign_id.batch_size
                if rec.campaign_id.override_batch_size
                else rec.product_tmpl_id.mrp_max_batch_size
            )

    @api.depends("is_batch_produced")
    def _compute_use_buffer(self):
        for rec in self:
            rec.use_buffer = rec.is_batch_produced

    @api.depends("bom_id")
    def _compute_downstream_product(self) -> None:
        for rec in self:
            rec.downstream_product_id = rec._get_downstream_product()

    @api.depends("production_ids", "production_ids.qty_produced")
    def _compute_fulfilled_qty(self):
        for rec in self:
            rec.fulfilled_qty = sum(rec.production_ids.mapped("qty_produced"))

    @api.depends(
        "upstream_line_ids",
        "upstream_line_ids.qty",
        "demand_ids",
        "demand_ids.target_qty",
    )
    def _compute_qty(self):
        for rec in self:
            previous_qty = rec.qty
            buffer = (1 + rec.buffer_percent) if rec.is_batch_produced else 1
            if rec.upstream_line_ids:
                quantities = [
                    line.qty * line.bom_id.get_factor_to_product(rec.product_id)
                    for line in rec.upstream_line_ids
                ]
                rec.qty = sum(quantities) * buffer
            elif rec.demand_ids:
                rec.qty = sum(rec.demand_ids.mapped("target_qty")) * buffer
            else:
                rec.qty = 0
            if rec.productions_created and rec.qty != previous_qty:
                rec._adjust_mos(rec.qty)

    @api.depends("production_ids", "production_ids.product_qty", "production_ids.state")
    def _compute_producing_qty(self):
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

    def _get_downstream_product(self) -> ProductProduct:
        self.ensure_one()
        if not self.bom_id:
            return self.env["product.product"]
        if self.product_tmpl_id.is_campaign_anchor:
            return self.env["product.product"]

        anchors: ProductProduct = (
            self.bom_id.bom_line_ids.filtered(
                lambda line: self.is_valid_bom_line_for_product(line)
            )
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

        for bom_line in self.bom_id.bom_line_ids.filtered(
            lambda x: self.is_valid_bom_line_for_product(x) and x.product_id.bom_ids
        ):
            downstream_product = bom_line.product_id
            downstream_bom = self.env["mrp.bom"]._bom_find(products=downstream_product)[
                downstream_product
            ]

            if not downstream_bom:
                continue

            downstream_qty = (self.qty / self.bom_id.product_qty) * bom_line.product_qty

            existing_downstream_line = self.campaign_id.line_ids.filtered(
                lambda line, ds_product=downstream_product, ds_bom=downstream_bom: (
                    line.product_id == ds_product and line.bom_id == ds_bom
                )
            )
            if existing_downstream_line:
                existing_downstream_line.qty += downstream_qty
                self.downstream_line_id = existing_downstream_line
                existing_downstream_line._construct_downstream_tree_line(depth + 1)

            else:
                new_downstream_line = self.env["mrp.campaign.line"].create(
                    {
                        "campaign_id": self.campaign_id.id,
                        "product_id": downstream_product.id,
                        "bom_id": downstream_bom.id,
                        "qty": downstream_qty,
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
        if self.is_batch_produced:
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
            own_factor = self.bom_id.get_factor_to_product(self.downstream_product_id)
            downstream_factor = self.downstream_line_id._get_anchor_factor()
            return own_factor * downstream_factor

    def _adjust_mos(self, new_quantity: float) -> None:
        self.ensure_one()

        # Separate MOs into those that can be adjusted/deleted and
        # those that are fixed (e.g., done or cancelled)
        # MOs in 'draft', 'confirmed', 'progress' states are considered adjustable.
        adjustable_mos = self.production_ids.filtered(
            lambda mo: mo.state in ["draft", "confirmed", "progress"]
        )
        fixed_mos = self.production_ids - adjustable_mos
        fixed_qty_produced = sum(fixed_mos.mapped("product_qty"))

        required_from_adjustable_mos = new_quantity - fixed_qty_produced

        if float_is_zero(
            new_quantity, precision_rounding=self.product_id.uom_id.rounding
        ):
            adjustable_mos.unlink()
            return

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

        if self.is_batch_produced:
            self._adjust_batch_mos(adjustable_mos, required_from_adjustable_mos)

        else:  # Not batch produced
            if not float_is_zero(
                required_from_adjustable_mos,
                precision_rounding=self.product_id.uom_id.rounding,
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
                    _wizard: ChangeProductionQty = (
                        self.env["change.production.qty"]
                        .create(
                            {
                                "mo_id": mo.id,
                                "product_qty": required_from_adjustable_mos,
                            }
                        )
                        .change_prod_qty()
                    )
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
    ):
        # 1. Determine the target structure of MOs required from adjustable quantity
        target_mo_quantities = []
        n_full_batches = int(required_from_adjustable_mos / self.batch_size)
        remaining_qty_for_partial = required_from_adjustable_mos % self.batch_size

        for _n in range(n_full_batches):
            target_mo_quantities.append(self.batch_size)
        if not float_is_zero(
            remaining_qty_for_partial,
            precision_rounding=self.product_id.uom_id.rounding,
        ):
            target_mo_quantities.append(remaining_qty_for_partial)
        target_mo_quantities.sort()  # Sort for easier comp and greedy matching

        # 2. Prepare current adjustable MOs,
        # sorted by quantity to facilitate matching
        current_adjustable_mo_list = adjustable_mos.sorted("product_qty")

        # Keep track of MOs that will be updated/kept
        mos_to_keep_or_update = self.env["mrp.production"]
        # Keep track of target quantities that have been assigned to an MO
        assigned_target_quantities_indices = [False] * len(target_mo_quantities)

        # Greedily match and update existing MOs to target quantities
        for _current_mo_idx, current_mo in enumerate(current_adjustable_mo_list):
            # Try to find a target quantity that matches
            # or can be assigned to this current_mo
            best_match_target_idx = -1
            for target_qty_idx, _target_qty in enumerate(target_mo_quantities):
                if not assigned_target_quantities_indices[target_qty_idx]:
                    # Simple greedy: take the first available target quantity
                    best_match_target_idx = target_qty_idx
                    break

            if best_match_target_idx != -1:
                target_qty = target_mo_quantities[best_match_target_idx]

                if not float_is_zero(
                    current_mo.product_qty - target_qty,
                    precision_rounding=self.product_id.uom_id.rounding,
                ):
                    # Quantity is different, use wizard to update
                    _wizard: ChangeProductionQty = (
                        self.env["change.production.qty"]
                        .create({"mo_id": current_mo.id, "product_qty": target_qty})
                        .change_prod_qty()
                    )

                mos_to_keep_or_update |= current_mo
                assigned_target_quantities_indices[best_match_target_idx] = True

        # 3. Delete excess adjustable MOs
        # Any adjustable MOs not in mos_to_keep_or_update are considered excess
        mos_to_unlink = adjustable_mos - mos_to_keep_or_update
        mos_to_unlink.unlink()

        # 4. Create new MOs for remaining unmatched target quantities
        values_to_create = []
        for target_qty_idx, target_qty in enumerate(target_mo_quantities):
            if not assigned_target_quantities_indices[target_qty_idx]:
                values_to_create.append(
                    {
                        "product_id": self.product_id.id,
                        "bom_id": self.bom_id.id,
                        "product_qty": target_qty,
                        "campaign_line_id": self.id,
                        "created_by_campaign": True,
                    }
                )

        if values_to_create:
            self.env["mrp.production"].create(values_to_create)
