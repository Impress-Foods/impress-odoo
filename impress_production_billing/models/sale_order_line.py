from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    production_ids = fields.One2many("mrp.production", "billing_sale_order_line_id")

    @api.constrains("product_id")
    def _check_product_id(self) -> None:
        for rec in self:
            if rec.production_ids:
                prod_billing_product = rec.production_ids.mapped("billing_product_id")
                if len(prod_billing_product) != 1:
                    raise ValidationError(
                        _("Not all productions match this billing product")
                    )
                elif prod_billing_product != rec.product_id:
                    raise ValidationError(
                        _(
                            "Cannot change the product of a sale order line "
                            "with linked productions!"
                        )
                    )
