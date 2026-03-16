import logging

from odoo.exceptions import ValidationError
from odoo.fields import Command

from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale.models.sale_order_line import SaleOrderLine
from odoo.addons.stock.models.stock_picking import StockPicking

from . import test_common

_logger = logging.getLogger(__name__)


class TestSaleOrder(test_common.TestCommon):
    def test_sale_order_no_deposit_product_configured(self) -> None:
        so: SaleOrder = self.so_model.create(
            {
                "partner_id": self.partner_w_deposit.id,
            }
        )

        self.env["res.config.settings"].create({"deposit_product": False}).execute()
        self.sol_model.create(
            {
                "order_id": so.id,
                "product_id": self.product_w_deposit.id,
                "product_uom_qty": 1.0,
            }
        )
        with self.assertRaises(ValidationError):
            so.action_confirm()

    def test_sale_order_with_deposit(self) -> None:
        so: SaleOrder = self.so_model.create(
            {
                "partner_id": self.partner_w_deposit.id,
            }
        )

        self.sol_model.create(
            {
                "order_id": so.id,
                "product_id": self.product_w_deposit.id,
                "product_uom_qty": 1.0,
            }
        )

        so.action_confirm()
        deposit_line: SaleOrderLine = so.order_line.filtered(
            lambda x: x.is_deposit_line
        )
        self.assertEqual(len(deposit_line), 1, "Deposit line not created")
        picking: StockPicking = so.picking_ids.filtered(
            lambda x: x.picking_type_code == "outgoing"
        )[0]
        picking.action_assign()
        picking.button_validate()

        # _ = so.deposit_value
        self.assertEqual(deposit_line.qty_delivered, 1.0, "Deposit line not delivered")

    def test_sale_order_partner_no_deposit(self) -> None:
        so: SaleOrder = self.so_model.create(
            {
                "partner_id": self.partner_wo_deposit.id,
            }
        )

        self.sol_model.create(
            {
                "order_id": so.id,
                "product_id": self.product_w_deposit.id,
                "product_uom_qty": 1.0,
            }
        )

        so.action_confirm()
        deposit_line: SaleOrderLine = so.order_line.filtered(
            lambda x: x.is_deposit_line
        )
        self.assertEqual(len(deposit_line), 0, "Deposit line created")

    def test_sale_order_product_no_deposit(self) -> None:
        so: SaleOrder = self.so_model.create(
            {
                "partner_id": self.partner_w_deposit.id,
            }
        )

        self.sol_model.create(
            {
                "order_id": so.id,
                "product_id": self.product_wo_deposit.id,
                "product_uom_qty": 1.0,
            }
        )

        so.action_confirm()
        deposit_line: SaleOrderLine = so.order_line.filtered(
            lambda x: x.is_deposit_line
        )
        self.assertEqual(len(deposit_line), 0, "Deposit line created")

    def test_sale_order_multiple_deposit_line(self) -> None:
        with self.assertRaises(ValidationError):
            self.so_model.create(
                {
                    "partner_id": self.partner_w_deposit.id,
                    "order_line": [
                        Command.create({"product_id": self.deposit_product.id}),
                        Command.create({"product_id": self.deposit_product.id}),
                    ],
                }
            )
        so = self.so_model.create(
            {
                "partner_id": self.partner_w_deposit.id,
                "order_line": [
                    Command.create({"product_id": self.deposit_product.id}),
                ],
            }
        )
        with self.assertRaises(ValidationError):
            so.write(
                {
                    "order_line": [
                        Command.create({"product_id": self.deposit_product.id})
                    ],
                }
            )
