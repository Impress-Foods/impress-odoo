import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    qty_multiple = fields.Integer("Quantity per case", default=1)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    qty_multiple = fields.Integer(
        "Quantity per case",
        compute="_compute_qty_multiple",
        inverse="_inverse_qty_multiple",
    )

    def _compute_qty_multiple(self):
        self._compute_template_field_from_variant_field("qty_multiple")

    def _inverse_qty_multiple(self):
        self._set_product_variant_field("qty_multiple")
