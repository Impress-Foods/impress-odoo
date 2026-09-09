from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    label_display_name = fields.Char(translate=True)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    label_display_name = fields.Char(
        compute="_compute_label_display_name",
        inverse="_inverse_label_display_name",
        translate=True,
    )

    def _compute_label_display_name(self):
        self._compute_template_field_from_variant_field("label_display_name")

    def _inverse_label_display_name(self):
        self._set_product_variant_field("label_display_name")
