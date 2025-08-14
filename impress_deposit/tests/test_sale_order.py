import logging

from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale.models.sale_order_line import SaleOrderLine
from odoo.addons.stock.models.stock_picking import Picking

from . import test_common

_logger = logging.getLogger(__name__)


class TestSaleOrder(test_common.TestCommon):  # type: ignore
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
                "product_uom": self.product_w_deposit.uom_id.id,
                "product_uom_qty": 1.0,
            }
        )

        so.action_confirm()
        # Force the triggering of the compute method,
        # not firing in tests for some reason
        _ = so.deposit_value

        deposit_line: SaleOrderLine = so.order_line.filtered(
            lambda x: x.is_deposit_line
        )
        self.assertEqual(len(deposit_line), 1, "Deposit line not created")
        picking: Picking = so.picking_ids.filtered(  # type: ignore
            lambda x: x.picking_type_code == "outgoing"
        )[0]
        picking.action_assign()
        picking.button_validate()

        # Force the triggering of the compute method,
        # not firing in tests for some reason
        _ = so.deposit_value
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
        # Force the triggering of the compute method,
        # not firing in tests for some reason
        _ = so.deposit_value

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
        # Force the triggering of the compute method,
        # not firing in tests for some reason
        _ = so.deposit_value

        deposit_line: SaleOrderLine = so.order_line.filtered(
            lambda x: x.is_deposit_line
        )
        self.assertEqual(len(deposit_line), 0, "Deposit line created")
