import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    deposit_value = fields.Monetary(
        string="Deposit", compute="_compute_deposit_value", store=True
    )

    @api.depends("order_line.qty_delivered", "order_line.product_uom_qty")
    def _compute_deposit_value(self):
        for record in self:
            if record._deposit_needed():
                record._handle_deposit()
            else:
                record.deposit_value = 0.0

    def _deposit_needed(self):
        # TODO: Figure out better way to differentiate between
        # eCom orders (both from Odoo and WooCommcerce)
        # and B2B orders.

        self.ensure_one()
        products_need_deposit = any(
            self.order_line.mapped(lambda x: x.product_id.requires_deposit)
        )
        partner_need_deposit = self.partner_id.requires_deposit
        order_stage = self.state not in ["cancel", "draft", "sent"]

        b2b = all([products_need_deposit, partner_need_deposit, order_stage])
        ecom = all([self.website_id])
        return any([b2b, ecom])

    def _handle_deposit(self):
        self.ensure_one()

        deposit_product_id = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("impress_deposit.deposit_product")
        )
        deposit_product = self.env["product.product"].browse(deposit_product_id)
        deposit_line = self.env["sale.order.line"].search(
            [("order_id", "=", self.id), ("product_id", "=", deposit_product_id)]
        )
        if len(deposit_line) == 0:
            deposit_line = self.env["sale.order.line"].create(
                [
                    {
                        "order_id": self.id,
                        "name": _("Deposit"),
                        "product_id": deposit_product.id,
                        "product_uom": deposit_product.uom_id.id,
                        "qty_delivered": self._compute_container_count(),
                        "product_uom_qty": self._compute_container_count(),
                        "is_deposit_line": True,
                    }
                ]
            )

        else:
            deposit_line = deposit_line[0]
            deposit_line.write(
                {
                    "qty_delivered": 0
                    if self.website_id
                    else self._compute_container_count(),
                    "product_uom_qty": self._compute_container_count(),
                }
            )
        self.deposit_value = deposit_line.price_total

    def _compute_container_count(self):
        total = 0
        for line in self.order_line:
            if line.product_id.requires_deposit:
                if self.website_id:
                    total += line.product_uom_qty * line.product_id.qty_multiple
                else:
                    total += line.qty_delivered * line.product_id.qty_multiple
        return total
