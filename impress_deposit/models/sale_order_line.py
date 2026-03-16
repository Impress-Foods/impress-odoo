from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_deposit_line = fields.Boolean(compute="_compute_is_deposit_line")

    @api.depends("product_id")
    def _compute_is_deposit_line(self) -> None:
        for line in self:
            deposit_product_id = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("impress_deposit.deposit_product")
            )
            line.is_deposit_line = line.product_id.id == deposit_product_id
