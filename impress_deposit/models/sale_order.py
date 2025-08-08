import logging

from odoo import _, api, fields, models

from odoo.addons.sale.models.sale_order_line import SaleOrderLine

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    deposit_value = fields.Monetary(
        string="Deposit",
        compute="_compute_deposit_value",
        store=True,
        depends=["order_line.qty_delivered", "order_line.product_uom_qty", "state"],
    )
    test = fields.Boolean(compute="_compute_test", store=True)

    @api.depends("state", "order_line")
    def _compute_test(self) -> None:
        _logger.warning("Test Compute Method")
        self.test = True

    @api.depends("order_line.qty_delivered", "order_line.product_uom_qty", "state")
    def _compute_deposit_value(self) -> None:
        _logger.warning("Computing deposit value")
        for record in self:
            if record._deposit_needed():
                deposit_line = record._get_deposit_line()
                deposit_line.write(
                    {
                        "qty_delivered": self._compute_container_count(),
                        "product_uom_qty": self._compute_container_count(),
                    }
                )
                record.deposit_value = deposit_line.price_total
            else:
                record.deposit_value = 0.0

    def _deposit_needed(self) -> bool:
        self.ensure_one()
        products_need_deposit = any(
            self.order_line.mapped(lambda x: x.product_id.requires_deposit)
        )
        partner_need_deposit = self.partner_id.requires_deposit
        order_stage = self.state not in ["cancel", "draft", "sent"]
        # _logger.warning(
        #     f"""product: {products_need_deposit} \n
        #         partner: {partner_need_deposit} \n
        #         stage: {order_stage}"""
        # )
        return all([products_need_deposit, partner_need_deposit, order_stage])

    def _get_deposit_line(self) -> SaleOrderLine:
        self.ensure_one()
        lines = self.order_line.filtered(lambda x: x.is_deposit_line)
        deposit_line = self.env["sale.order.line"]
        match len(lines):
            case 0:
                deposit_product_id = int(
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("impress_deposit.deposit_product")
                )
                deposit_product = self.env["product.product"].browse(deposit_product_id)
                deposit_line = self.env["sale.order.line"].create(
                    [
                        {
                            "order_id": self.id,
                            "name": _("Deposit"),
                            "product_id": deposit_product.id,
                            "product_uom": deposit_product.uom_id.id,
                            "qty_delivered": 0,
                            "product_uom_qty": 0,
                            "is_deposit_line": True,
                        }
                    ]
                )
            case 1:
                deposit_line = lines[0]

            case _:
                deposit_line = lines[0]
                (lines - deposit_line).unlink()

        return deposit_line

    def _compute_container_count(self) -> int:
        total = 0
        for line in self.order_line:
            total += line.get_deposit_container_qty()

        return total
