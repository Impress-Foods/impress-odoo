import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    billing_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Billing Product",
        domain=[("type", "=", "service")],
    )

    def get_production_billing_product(self):
        self.ensure_one()

        if self.billing_product_id:
            return self.billing_product_id

        if self.product_id:
            base_reference = self.product_id.default_code
        else:
            base_reference = self.product_tmpl_id.default_code

        reference_to_match = "S" + base_reference[1:]
        matching_product = self.env["product.product"].search(
            [("default_code", "=", reference_to_match)]
        )
        if matching_product:
            return matching_product
        else:
            raise ValidationError(
                self.env._(
                    "No matching service product found."
                    f"Expected product with reference {reference_to_match}"
                )
            )
