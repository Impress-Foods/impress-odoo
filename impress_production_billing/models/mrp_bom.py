import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    billing_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Billing Product",
        domain=[("type", "=", "service")],
    )

    _sql_constraints = [
        (
            "unique_billing_product",
            "UNIQUE (billing_product_id)",
            "A billing product can only be assigned to one end product's BOM.",
        ),
    ]
