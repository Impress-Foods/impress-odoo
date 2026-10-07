from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    net_weight = fields.Float()

    label_name = fields.Char(
        string="Name on labels",
        translate=True,
        help="This name will be used on labels instead of the product name.",
        compute="_compute_label_name",
        inverse="_inverse_label_name",
    )

    external_code = fields.Char(
        compute="_compute_external_code", inverse="_inverse_external_code"
    )

    def _compute_label_name(self):
        self._compute_template_field_from_variant_field("label_name")

    def _inverse_label_name(self):
        self._set_product_variant_field("label_name")

    def _compute_external_code(self):
        self._compute_template_field_from_variant_field("external_code")

    def _inverse_external_code(self):
        self._set_product_variant_field("external_code")


class ProductProduct(models.Model):
    _inherit = "product.product"

    label_name = fields.Char(
        string="Name on labels",
        translate=True,
        help="This name will be used on labels instead of the product name.",
    )

    external_code = fields.Char()
