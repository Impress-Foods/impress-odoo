from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleOrderLinePickingSync(TransactionCase):
    """A confirmed sale order line must keep its pending delivery in sync when
    its ordered quantity changes, instead of creating an extra picking (on
    increase) or a return from the customer location (on decrease)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.warehouse.delivery_steps = "pick_ship"
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Picking sync product",
                "type": "consu",
                "is_storable": True,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Picking sync customer"})
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.warehouse.lot_stock_id, 1000.0
        )

    def _create_confirmed_order(self, qty=10.0, uom=None, printed=False):
        line_vals = {
            "product_id": self.product.id,
            "product_uom_qty": qty,
            "price_unit": 1.0,
        }
        if uom:
            line_vals["product_uom_id"] = uom.id
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [Command.create(line_vals)],
            }
        )
        order.action_confirm()
        if printed:
            # Marking the picking as printed is what makes the standard flow
            # create a new picking/return instead of reusing the pending one.
            self._pick_picking(order).printed = True
        return order

    def _pick_picking(self, order):
        return order.picking_ids.filtered(
            lambda picking: picking.picking_type_id == self.warehouse.pick_type_id
        )

    def _return_pickings(self, order):
        return order.picking_ids.filtered(
            lambda picking: picking.location_id == self.customer_location
        )

    def test_confirmation_creates_single_pick(self):
        order = self._create_confirmed_order(10.0)
        self.assertEqual(len(order.picking_ids), 1)
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 10.0)

    def test_increase_updates_pending_pick(self):
        order = self._create_confirmed_order(10.0, printed=True)
        order.order_line.product_uom_qty = 15.0
        self.assertEqual(len(order.picking_ids), 1)
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 15.0)

    def test_decrease_updates_pending_pick(self):
        order = self._create_confirmed_order(10.0, printed=True)
        order.order_line.product_uom_qty = 4.0
        self.assertEqual(len(order.picking_ids), 1)
        self.assertFalse(self._return_pickings(order))
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 4.0)

    def test_decrease_to_zero_updates_pending_pick(self):
        order = self._create_confirmed_order(10.0, printed=True)
        order.order_line.product_uom_qty = 0.0
        self.assertEqual(len(order.picking_ids), 1)
        self.assertFalse(self._return_pickings(order))
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 0.0)

    def test_increase_then_decrease_keeps_single_pick(self):
        order = self._create_confirmed_order(10.0, printed=True)
        order.order_line.product_uom_qty = 25.0
        order.order_line.product_uom_qty = 6.0
        self.assertEqual(len(order.picking_ids), 1)
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 6.0)

    def test_uom_is_converted_on_move(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        order = self._create_confirmed_order(2.0, uom=dozen, printed=True)
        # 2 dozens must be stored as 24 units on the stock move.
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 24.0)
        order.order_line.product_uom_qty = 3.0
        self.assertEqual(self._pick_picking(order).move_ids.product_uom_qty, 36.0)

    def test_validated_pick_falls_back_to_standard_flow(self):
        order = self._create_confirmed_order(10.0)
        pick = self._pick_picking(order)
        pick.move_ids.write({"quantity": 10.0, "picked": True})
        pick._action_done()

        line = order.order_line
        # A validated move can no longer be reworked in place.
        self.assertFalse(line._apply_qty_change_on_pending_moves())

        line.product_uom_qty = 8.0
        self.assertEqual(pick.move_ids.product_uom_qty, 10.0)
