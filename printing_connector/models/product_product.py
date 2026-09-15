from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    label_display_name = fields.Char(translate=True)
    label_extra_data = fields.Char(translate=True)
    label_format = fields.Char()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    label_display_name = fields.Char(
        compute="_compute_label_display_name",
        inverse="_inverse_label_display_name",
        translate=True,
    )

    label_extra_data = fields.Char(
        compute="_compute_label_extra_data",
        inverse="_inverse_label_extra_data",
        translate=True,
    )

    label_format = fields.Char(
        compute="_compute_label_format",
        inverse="_inverse_label_format",
    )

    def _compute_label_display_name(self):
        self._compute_template_field_from_variant_field("label_display_name")

    def _inverse_label_display_name(self):
        self._set_product_variant_field("label_display_name")

    def _compute_label_extra_data(self):
        self._compute_template_field_from_variant_field("label_extra_data")

    def _inverse_label_extra_data(self):
        self._set_product_variant_field("label_extra_data")

    def _compute_label_format(self):
        self._compute_template_field_from_variant_field("label_format")

    def _inverse_label_format(self):
        self._set_product_variant_field("label_format")
