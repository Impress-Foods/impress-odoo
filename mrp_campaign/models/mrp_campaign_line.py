import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
from odoo.addons.product.models.product_product import ProductProduct

_logger = logging.getLogger(__name__)


class CampaignLine(models.Model):
    _name = "mrp.campaign.line"
    _description = "Campaign breakdown line"

    campaign_id = fields.Many2one("mrp.campaign", ondelete="cascade")
    production_ids = fields.One2many("mrp.production", "campaign_line_id")

    product_id = fields.Many2one("product.product")
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id")
    product_template_variant_value_ids = fields.Many2many(
        related="product_id.product_template_variant_value_ids"
    )
    qty = fields.Float()
    bom_id = fields.Many2one("mrp.bom")

    is_batch_produced = fields.Boolean(compute="_compute_is_batch_produced")
    batch_size = fields.Float(compute="_compute_batch_size")

    use_buffer = fields.Boolean(compute="_compute_use_buffer")
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
        _logger.warning(f"Product: {self.product_id.name}")

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
            _logger.warning(f"Processing line for {rec.product_id.name}")
            values += rec._make_production_order()
        self.env["mrp.production"].create(values)

    def _make_production_order(self) -> list[dict]:
        self.ensure_one()
        values = []
        if self.is_batch_produced:
            remaining_qty = self.qty * (1 + self.buffer_percent)

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
