import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
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

    @api.depends("product_id")
    def _compute_is_batch_produced(self):
        for rec in self:
            rec.is_batch_produced = rec.product_tmpl_id.mrp_max_batch_size != 0

    @api.depends("product_id")
    def _compute_batch_size(self):
        for rec in self:
            rec.batch_size = (
                rec.campaign_id.override_batch_size
                or rec.product_tmpl_id.mrp_max_batch_size
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
            if rec.qty != previous_qty:
                rec._adjust_mos(rec.qty)

    @api.depends("production_ids", "production_ids.product_qty")
    def _compute_producing_qty(self):
        for rec in self:
            rec.producing_qty = sum(rec.production_ids.mapped("product_qty"))

    def _get_downstream_product(self) -> ProductProduct:
        self.ensure_one()
        if not self.bom_id:
            raise UserError(_("Product %s has no BoM" % self.product_id.name))

        anchors: ProductProduct = (
            self.bom_id.bom_line_ids.filtered(
                lambda line: self.is_valid_bom_line_for_product(self.product_id, line)
            )
            .mapped("product_id")
            .filtered("anchor_product_id")
        )

        if not anchors:
            return self.env["product.product"]
        if len(anchors) != 1:
            return UserError(
                _(
                    "Could not resolve downstream product "
                    "for %(product) with BoM %(bom)",
                    {
                        "product": self.product_id,
                        "bom": self.bom_id,
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
            lambda x: (
                self.is_valid_bom_line_for_product(self.product_id, x)
                and x.product_id.bom_ids
            )
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

    def make_production_order(self) -> None:
        values = []
        for rec in self:
            values += rec._make_production_order()
        self.env["mrp.production"].create(values)

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

    def is_valid_bom_line_for_product(
        self, product_id: ProductProduct, bom_line: MrpBomLine
    ) -> bool:
        self.ensure_one()
        bom_line_variant_ids = bom_line.bom_product_template_attribute_value_ids

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
        if self.is_batch_produced:
            full_mos = self.production_ids.filtered(
                lambda x: x.product_qty == self.batch_size
            )
            _logger.warning(self.production_ids)
            _logger.warning(full_mos)

            partial_mos = self.production_ids - full_mos
            _logger.warning(partial_mos)
            full_mos_qty = sum(full_mos.mapped("product_qty"))
            _logger.warning(f"new_qty: {new_quantity} vs full mos {full_mos_qty}")

            if len(partial_mos) > 1:
                raise ValidationError(_("Multiple partial MOs"))

            if new_quantity < full_mos_qty:
                # we now have to cancel MOs and set the quantities to match
                _logger.warning("complicated path")
                needed_full_mos = new_quantity // self.batch_size
                remainder = new_quantity % self.batch_size
                needed_mos = needed_full_mos + 1 if remainder else 0
                n_mos_to_delete = len(self.production_ids) - needed_mos
                mos_possible_to_delete = self.production_ids.filtered_domain(
                    [("state", "in", ["draft", "confirmed", "progress"])]
                )
                if len(mos_possible_to_delete) < n_mos_to_delete:
                    raise ValidationError(
                        _("Insufficient number of possible MOs to delete")
                    )

                if partial_mos[0] and partial_mos[0] in mos_possible_to_delete:
                    n_mos_to_delete -= 1
                    partial_mos.unlink()
                mos_to_delete = full_mos[:n_mos_to_delete]
                full_mos -= mos_to_delete
                mos_to_delete.unlink()
                if remainder:
                    full_mos[0].write({"product_qty": remainder})

            else:
                _logger.warning("simple path")
                remainder = new_quantity - full_mos_qty
                if remainder <= self.batch_size:
                    _wizard: ChangeProductionQty = (
                        self.env["change.production.qty"]
                        .create({"mo_id": partial_mos[0].id, "product_qty": remainder})
                        .change_prod_qty()
                    )
                else:
                    # TODO: handle existing partial MO
                    n_new_mos, overflow = divmod(new_quantity, self.batch_size)
                    values = [
                        {
                            "product_id": self.product_id.id,
                            "bom_id": self.bom_id.id,
                            "product_qty": self.batch_size,
                            "campaign_line_id": self.id,
                            "created_by_campaign": True,
                        }
                        for _n in range(n_new_mos)
                    ]
                    if overflow:
                        values.append(
                            {
                                "product_id": self.product_id.id,
                                "bom_id": self.bom_id.id,
                                "product_qty": overflow,
                                "campaign_line_id": self.id,
                                "created_by_campaign": True,
                            }
                        )
                    self.env["mrp.production"].create()

        elif len(self.production_ids) > 1:
            raise ValidationError(_("Standard line with multiple MOs"))
        elif len(self.production_ids) == 1:
            mo = self.production_ids[0]
            _wizard: ChangeProductionQty = (
                self.env["change.production.qty"]
                .create({"mo_id": mo.id, "product_qty": new_quantity})
                .change_prod_qty()
            )
