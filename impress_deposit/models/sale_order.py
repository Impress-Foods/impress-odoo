import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    deposit_line_id = fields.Many2one(
        "sale.order.line",
        string="Deposit Line",
        compute="_compute_deposit_line_id",
        store=True,
    )
    deposit_value = fields.Monetary(
        string="Deposit",
        compute="_compute_deposit_value",
        store=True,
        depends=[
            "order_line",
            "order_line.product_uom_qty",
            "order_line.is_deposit_line",
            "deposit_line_id",
            "deposit_line_id.price_total",
            "state",
        ],
    )

    @api.depends("order_line", "order_line.is_deposit_line")
    def _compute_deposit_line_id(self):
        for record in self:
            deposit_lines = record.order_line.filtered(lambda x: x.is_deposit_line)
            if len(deposit_lines) > 1:
                deposit_lines[1:].unlink()
            record.deposit_line_id = deposit_lines[0] if deposit_lines else False

    @api.constrains("order_line")
    def _constrain_single_deposit_line(self):
        for record in self:
            deposit_lines = record.order_line.filtered(lambda x: x.is_deposit_line)
            if len(deposit_lines) > 1:
                raise ValidationError(
                    self.env._("Only one deposit line is allowed per sale order.")
                )

    @api.depends(
        "order_line",
        "order_line.product_uom_qty",
        "order_line.is_deposit_line",
        "deposit_line_id",
        "deposit_line_id.price_total",
        "state",
    )
    def _compute_deposit_value(self) -> None:
        for record in self:
            if record._deposit_needed():
                if not record.deposit_line_id:
                    record._create_deposit_line()
                if record.deposit_line_id:
                    container_qty = sum(
                        record.order_line.filtered(
                            lambda line: line.product_id.requires_deposit
                        ).mapped(
                            lambda line: (
                                line.product_uom_qty * line.product_id.qty_multiple
                            )
                        )
                    )
                    record.deposit_line_id.update(
                        {
                            "product_uom_qty": container_qty,
                        }
                    )
                    record.deposit_value = record.deposit_line_id.price_total
            else:
                record.deposit_value = 0.0

    def action_confirm(self):
        result = super().action_confirm()
        for record in self:
            if record._deposit_needed() and not record.deposit_line_id:
                record._create_deposit_line()
        return result

    def _create_deposit_line(self):
        self.ensure_one()
        deposit_product_id = self._get_deposit_product()
        if not deposit_product_id:
            raise ValidationError(
                self.env._(
                    "Deposit product is not configured. "
                    "Configure it before creating an SO with container deposit"
                )
            )

        deposit_product = self.env["product.product"].browse(deposit_product_id)
        container_qty = sum(
            self.order_line.filtered(
                lambda line: line.product_id.requires_deposit
            ).mapped(lambda line: line.product_uom_qty * line.product_id.qty_multiple)
        )
        self.env["sale.order.line"].create(
            {
                "order_id": self.id,
                "name": self.env._("Deposit"),
                "product_id": deposit_product.id,
                "product_uom_qty": container_qty,
                "qty_delivered": 0,
                "is_deposit_line": True,
                "sequence": 999,
            }
        )

    def _deposit_needed(self) -> bool:
        self.ensure_one()
        products_need_deposit = any(
            self.order_line.mapped(lambda x: x.product_id.requires_deposit)
        )
        partner_need_deposit = self.partner_id.requires_deposit
        order_stage = self.state not in ["cancel", "draft", "sent"]
        return all([products_need_deposit, partner_need_deposit, order_stage])

    @api.model
    def _get_deposit_product(self):
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("impress_deposit.deposit_product")
        )
