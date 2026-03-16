import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Product(models.Model):
    _inherit = "product.product"

    requires_deposit = fields.Boolean()
    qty_multiple = fields.Integer("Quantity for deposit")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    requires_deposit = fields.Boolean(
        compute="_compute_requires_deposit",
        inverse="_inverse_requires_deposit",
    )
    qty_multiple = fields.Integer(
        "Quantity for deposit",
        compute="_compute_qty_multiple",
        inverse="_inverse_qty_multiple",
    )

    def _compute_requires_deposit(self):
        self._compute_template_field_from_variant_field("requires_deposit")

    def _inverse_requires_deposit(self):
        self._set_product_variant_field("requires_deposit")

    def _compute_qty_multiple(self):
        self._compute_template_field_from_variant_field("qty_multiple")

    def _inverse_qty_multiple(self):
        self._set_product_variant_field("qty_multiple")
