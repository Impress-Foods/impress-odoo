"""Cancelling units of a Costco order: the order shrinks and Costco is told why."""

from unittest import mock

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tools import mute_logger

from .common import TRACKING, CostcoShipmentCase


class TestCancellation(CostcoShipmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reason = cls.env.ref("edi_rithum_costco.cancel_reason_out_of_stock")

    def _cancellation(self, order, quantity, reason=None, note=""):
        action = order.action_costco_cancel()
        context = action["context"]
        cancellation = self.env["edi.rithum.costco.cancellation"].create(
            {
                "order_id": context["default_order_id"],
                "reason_id": (reason or self.reason).id,
                "note": note,
                "line_ids": context["default_line_ids"],
            }
        )
        cancellation.line_ids.quantity = quantity
        return cancellation

    def _confirm(self, cancellation):
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            cancellation.action_confirm()
        return send

    def _components(self, picking):
        """Quantity of each kit component still to move on the delivery."""
        return {
            move.product_id.default_code: move.product_uom_qty
            for move in picking.move_ids
        }

    def _message(self, cancellation):
        return self._text(cancellation.exchange_record_ids)

    def test_the_cancel_reason_codes_come_from_costco(self):
        codes = self.env["edi.rithum.costco.code"].search(
            [("code_type", "=", "cancel_reason")]
        )
        self.assertEqual(len(codes), 13)
        self.assertIn("out_of_stock", codes.mapped("code"))
        self.assertIn("bad_sku", codes.mapped("code"))

    def test_cancelling_units_reduces_the_order_and_tells_costco(self):
        order, picking = self._order(kits=5)
        cancellation = self._cancellation(order, 2, note="none left")
        send = self._confirm(cancellation)
        send.assert_called_once()
        self.assertEqual(order.order_line.product_uom_qty, 3)
        self.assertEqual(self._components(picking), {"COMP-A": 6, "COMP-B": 3})
        self.assertEqual(cancellation.state, "done")
        record = cancellation.exchange_record_ids
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._message(cancellation)
        self.assertIn(f"PRF*{order.client_order_ref}~", text)
        self.assertIn("SN1**0*EA**2*EA**ID~", text)
        self.assertIn("REF*TD*out_of_stock*none left~", text)
        for absent in ("TD1*", "TD5*", "DTM*", "N1*", "MAN*", "REF*IV"):
            self.assertNotIn(f"\n{absent}", text)
        self.assertTrue(record.x12_control_number)

    def test_cancelling_the_whole_order_cancels_the_order_and_its_delivery(self):
        order, picking = self._order(kits=3)
        cancellation = self._cancellation(order, 3)
        send = self._confirm(cancellation)
        send.assert_called_once()
        self.assertEqual(order.state, "cancel")
        self.assertEqual(picking.state, "cancel")
        self.assertEqual(order.order_line.product_uom_qty, 3)
        self.assertIn("SN1**0*EA**3*EA**ID~", self._message(cancellation))

    def test_a_partial_cancellation_leaves_the_order_confirmed(self):
        order, picking = self._order(kits=3)
        self._confirm(self._cancellation(order, 1))
        self.assertEqual(order.state, "sale")
        self.assertNotEqual(picking.state, "cancel")

    def test_every_line_must_be_fully_cancelled_to_cancel_the_order(self):
        order, __ = self._order(kits=3)
        ice = self._storable("ICE")
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": ice.id,
                "product_uom_qty": 2,
                "price_unit": 0,
            }
        )
        self._confirm(self._cancellation(order, 3))
        self.assertEqual(order.state, "cancel")

    def test_the_standard_cancel_is_refused_while_costco_is_owed_units(self):
        order, __ = self._order(kits=3)
        with self.assertRaisesRegex(UserError, "Cancel with Costco"):
            order.action_cancel()
        self.assertEqual(order.state, "sale")

    def test_the_standard_cancel_works_for_other_orders(self):
        order, __ = self._order(kits=3, from_edi=False)
        order.action_cancel()
        self.assertEqual(order.state, "cancel")

    def test_the_standard_cancel_works_once_nothing_is_left_to_deliver(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        self.assertFalse(order.costco_can_cancel)
        order.action_cancel()

    def test_what_is_left_after_a_partial_shipment_can_be_cancelled(self):
        order, picking = self._order(kits=5)
        self._pack(picking, [2])
        self._validate(picking, tracking=TRACKING[:1])
        backorder = order.picking_ids - picking
        self.assertEqual(self._components(backorder), {"COMP-A": 6, "COMP-B": 3})
        cancellation = self._cancellation(order, 3)
        self.assertEqual(cancellation.line_ids.open_quantity, 3)
        self._confirm(cancellation)
        self.assertEqual(order.order_line.product_uom_qty, 2)
        self.assertEqual(order.order_line.qty_delivered, 2)
        self.assertIn("SN1**0*EA**3*EA**ID~", self._message(cancellation))
        self.assertFalse(order.costco_can_cancel)

    def test_more_than_the_open_quantity_is_refused(self):
        order, __ = self._order(kits=3)
        cancellation = self._cancellation(order, 4)
        with self.assertRaises(UserError):
            self._confirm(cancellation)
        self.assertEqual(order.order_line.product_uom_qty, 3)
        self.assertEqual(cancellation.state, "draft")

    def test_cancelling_nothing_is_refused(self):
        order, __ = self._order(kits=3)
        with self.assertRaises(UserError):
            self._confirm(self._cancellation(order, 0))

    def test_delivered_units_cannot_be_cancelled(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        self.assertFalse(order.costco_can_cancel)
        with self.assertRaises(UserError):
            order.action_costco_cancel()

    def test_an_order_that_did_not_come_from_costco_has_no_cancel_action(self):
        order, __ = self._order(kits=3, from_edi=False)
        self.assertFalse(order.costco_can_cancel)

    def test_a_failed_send_keeps_the_cancellation_and_can_be_sent_again(self):
        order, __ = self._order(kits=3)
        # the order's file is what the cancellation is addressed from
        file = order.origin_exchange_record_id.exchange_file
        order.origin_exchange_record_id.exchange_file = False
        cancellation = self._cancellation(order, 1)
        send = self._confirm(cancellation)
        send.assert_not_called()
        self.assertEqual(order.order_line.product_uom_qty, 2)
        self.assertEqual(cancellation.state, "done")
        self.assertIn(
            "not created from an EDI file",
            cancellation.exchange_record_ids.exchange_error,
        )
        self.assertIn(
            "could not be sent", " ".join(cancellation.message_ids.mapped("body"))
        )
        order.origin_exchange_record_id.exchange_file = file
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            cancellation.send()
        send.assert_called_once()
        self.assertEqual(len(cancellation.exchange_record_ids), 2)

    def test_the_cancel_button_is_on_the_order_form(self):
        arch = self.env["sale.order"].get_view(view_type="form")["arch"]
        self.assertIn('name="action_costco_cancel"', arch)

    def test_a_reason_must_be_chosen(self):
        order, __ = self._order(kits=3)
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            self.env["edi.rithum.costco.cancellation"].create({"order_id": order.id})

    def test_a_salesman_can_cancel_and_the_message_is_sent(self):
        user = self.env["res.users"].create(
            {
                "name": "Salesman",
                "login": "salesman_costco",
                "group_ids": [
                    (
                        6,
                        0,
                        [self.env.ref("sales_team.group_sale_salesman_all_leads").id],
                    )
                ],
            }
        )
        order, __ = self._order(kits=3)
        cancellation = self._cancellation(order, 1).with_user(user)
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            cancellation.action_confirm()
        send.assert_called_once()
        self.assertFalse(cancellation.exchange_record_ids.exchange_error)

    def _salesman(self, manager=False):
        group = "sale_manager" if manager else "sale_salesman_all_leads"
        return self.env["res.users"].create(
            {
                "name": "Sales user",
                "login": f"sales_{group}",
                "group_ids": [(6, 0, [self.env.ref(f"sales_team.group_{group}").id])],
            }
        )

    def test_cancellations_and_their_lines_are_deleted_by_managers_only(self):
        order, __ = self._order(kits=3)
        salesman, manager = self._salesman(), self._salesman(manager=True)
        cancellation = self._cancellation(order, 1)
        with self.assertRaises(AccessError):
            cancellation.line_ids.with_user(salesman).unlink()
        with self.assertRaises(AccessError):
            cancellation.with_user(salesman).unlink()
        cancellation.with_user(manager).unlink()
        self.assertFalse(cancellation.exists())
        self.assertFalse(
            self.env["edi.rithum.costco.cancellation.line"].search(
                [("cancellation_id", "=", cancellation.id)]
            )
        )

    def test_only_an_order_created_from_a_costco_file_is_a_costco_order(self):
        costco, __ = self._order(kits=3)
        other, __ = self._order(kits=3, from_edi=False)
        self.assertTrue(costco._costco_is_order())
        self.assertFalse(other._costco_is_order())
        # a delivery without a sale order has an empty one
        self.assertFalse(self.env["sale.order"].browse()._costco_is_order())

    def test_an_order_from_another_partners_file_is_not_a_costco_order(self):
        order, __ = self._order(kits=3)
        order.origin_exchange_record_id.rithum_partner_id = self.env[
            "edi.rithum.partner"
        ].create(
            {
                "name": "Another retailer",
                "x12_id": "OTHERRETAILER01",
                "map_set": "edi_rithum_costco/x12_maps",
                "intake_model": "edi.rithum.intake",
            }
        )
        self.assertFalse(order._costco_is_order())
        self.assertFalse(order.costco_can_cancel)
