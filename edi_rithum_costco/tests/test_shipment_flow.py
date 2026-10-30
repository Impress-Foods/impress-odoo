"""A finished Costco delivery sends its shipment confirmation, or says why not."""

import re
from unittest import mock

from odoo.exceptions import UserError

from .common import TRACKING, CostcoShipmentCase


class TestShipmentFlow(CostcoShipmentCase):
    def _confirmations(self, picking):
        return picking.exchange_record_ids.filtered(
            lambda r: r.type_id.code == "costco_856_out"
        )

    def _confirmation(self, picking):
        return self._confirmations(picking)

    def test_a_finished_delivery_sends_the_confirmation(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [2, 1])
        send = self._validate(picking)
        self.assertEqual(picking.state, "done")
        record = self._confirmation(picking)
        send.assert_called_once()
        text = self._text(record)
        self.assertIn(f"PRF*{order.client_order_ref}~", text)
        self.assertIn("TD5*B****UPSN_CG~", text)
        self.assertIn("N1*WH**54*2001~", text)
        self.assertIn("TD1******A3*", text)
        self.assertIn(f"MAN*CP*{TRACKING[0]}~", text)
        self.assertIn(f"MAN*CP*{TRACKING[1]}~", text)
        # one item holds the three kits, and lists both boxes it travelled in
        self.assertEqual(text.count("LIN*"), 1)
        self.assertIn("LIN*0001*VN*KIT-1*SK*COSTCO-1~", text)
        self.assertIn("SN1**3*EA*****AC~", text)
        self.assertEqual(text.count("MAN*CP*"), 2)
        self.assertFalse(record.exchange_error)
        # the partner's 997 will name this file by its control number
        control = self._text(record).split("~")[0].split("*")[13]
        self.assertEqual(record.x12_control_number, str(int(control)))
        self.assertEqual(record.exchange_filename, f"HUB{int(control):09d}.intchg")

    def test_components_that_do_not_make_whole_kits_are_not_sent(self):
        __, picking = self._order(kits=3)
        packages = self._pack(picking, [2, 1])
        line = picking.move_line_ids.filtered(
            lambda line: (
                line.result_package_id == packages[0]
                and line.product_id.default_code == "COMP-B"
            )
        )
        line.quantity = 1  # two kits' worth of A but only one B
        send = self._validate(picking)
        self.assertEqual(picking.state, "done")
        send.assert_not_called()
        record = self._confirmation(picking)
        self.assertIn("do not make whole kits", record.exchange_error)
        self.assertIn("could not be sent", " ".join(picking.message_ids.mapped("body")))

    def test_a_missing_tracking_number_is_not_sent(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [2, 1])
        send = self._validate(picking, tracking=TRACKING[:1])
        self.assertEqual(picking.state, "done")
        send.assert_not_called()
        self.assertIn("tracking number", self._confirmation(picking).exchange_error)

    def test_a_carrier_without_a_costco_code_is_not_sent(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        carrier = self.carrier.copy({"name": "Other", "costco_shipping_method": False})
        send = self._validate(picking, tracking=TRACKING[:1], carrier=carrier)
        send.assert_not_called()
        self.assertIn(
            "Costco shipping method", self._confirmation(picking).exchange_error
        )

    def test_an_item_outside_a_package_is_not_sent(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        picking.move_line_ids.result_package_id = False
        send = self._validate(picking, tracking=TRACKING[:1])
        send.assert_not_called()
        self.assertIn("package", self._confirmation(picking).exchange_error)

    def test_a_delivery_of_an_order_that_did_not_come_from_costco_is_ignored(self):
        __, picking = self._order(kits=3, from_edi=False)
        self._pack(picking, [3])
        send = self._validate(picking, tracking=TRACKING[:1])
        send.assert_not_called()
        self.assertFalse(self._confirmation(picking))

    def test_a_partial_shipment_confirms_what_left(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [2])
        picking.write(
            {"carrier_id": self.carrier.id, "carrier_tracking_ref": TRACKING[0]}
        )
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            picking.with_context(
                skip_immediate=True, skip_backorder=True
            ).button_validate()
        record = self._confirmation(picking)
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._text(record)
        self.assertIn("SN1**2*EA*****AC~", text)
        backorder = order.picking_ids - picking
        self.assertEqual(len(backorder), 1)

    def test_a_delivery_without_a_weight_is_not_sent(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3], weight=0.0)
        send = self._validate(picking, tracking=TRACKING[:1])
        send.assert_not_called()
        self.assertIn("no shipping weight", self._confirmation(picking).exchange_error)

    def test_the_weight_goes_out_in_pounds(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3], weight=10.0)
        self._validate(picking, tracking=TRACKING[:1])
        text = self._text(self._confirmation(picking))
        weight = float(text.split("TD1******A3*")[1].split("*")[0])
        in_kg = self.env[
            "product.template"
        ]._get_weight_uom_name_from_ir_config_parameter()
        self.assertAlmostEqual(weight, 22.05 if in_kg == "kg" else 10.0, places=2)

    def test_packaging_material_travels_but_is_not_confirmed(self):
        order, picking = self._order(kits=3)
        ice = self._storable("ICE")
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": ice.id,
                "product_uom_qty": 2,
                "price_unit": 0,
            }
        )
        self.assertEqual(order.picking_ids, picking)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        record = self._confirmation(picking)
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._text(record)
        self.assertNotIn("ICE", text)
        self.assertEqual(text.count("LIN*"), 1)
        self.assertIn("SN1**3*EA*****AC~", text)

    def test_a_plain_product_is_confirmed_by_its_quantity(self):
        self._storable("PLAIN-1")
        __, picking = self._order(kits=4, sku="PLAIN-1")
        self._pack(picking, [4])
        self._validate(picking, tracking=TRACKING[:1])
        record = self._confirmation(picking)
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._text(record)
        self.assertIn("LIN*0001*VN*PLAIN-1*SK*COSTCO-1~", text)
        self.assertIn("SN1**4*EA*****AC~", text)

    def _isa_control(self, record):
        return self._text(record).split("~")[0].split("*")[13]

    def test_resending_creates_a_new_confirmation_with_a_new_control_number(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            action = picking.action_costco_resend_confirmation()
        records = self._confirmations(picking)
        self.assertEqual(len(records), 2)
        send.assert_called_once()
        first, second = records.sorted("id")
        self.assertNotEqual(self._isa_control(first), self._isa_control(second))
        self.assertEqual(action["params"]["type"], "success")

    def test_resending_after_fixing_a_failure_sends_it(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        carrier = self.carrier.copy(
            {"name": "No code", "costco_shipping_method": False}
        )
        self._validate(picking, tracking=TRACKING[:1], carrier=carrier)
        failed = self._confirmation(picking)
        self.assertTrue(failed.exchange_error)
        picking.carrier_id = self.carrier
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            action = picking.action_costco_resend_confirmation()
        send.assert_called_once()
        self.assertEqual(action["params"]["type"], "success")
        records = self._confirmations(picking).sorted("id")
        self.assertEqual(len(records), 2)
        self.assertFalse(records[-1].exchange_error)

    def test_resending_an_incomplete_delivery_reports_what_is_missing(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        picking.carrier_tracking_ref = False
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            action = picking.action_costco_resend_confirmation()
        send.assert_not_called()
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("tracking number", action["params"]["message"])

    def test_the_button_shows_only_for_a_finished_costco_delivery(self):
        __, picking = self._order(kits=3)
        self.assertFalse(picking.costco_can_confirm)  # not done yet
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        self.assertTrue(picking.costco_can_confirm)
        __, other = self._order(kits=3, from_edi=False)
        self._pack(other, [3])
        self._validate(other, tracking=TRACKING[:1])
        self.assertFalse(other.costco_can_confirm)

    def test_resending_a_delivery_that_is_not_costco_s_is_refused(self):
        __, picking = self._order(kits=3, from_edi=False)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        with self.assertRaises(UserError):
            picking.action_costco_resend_confirmation()

    def test_the_resend_button_is_on_the_delivery_form(self):
        arch = self.env["stock.picking"].get_view(view_type="form")["arch"]
        self.assertIn('name="action_costco_resend_confirmation"', arch)

    def test_a_warehouse_without_a_rithum_id_is_not_sent(self):
        self.warehouse.costco_warehouse_code = False
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        send = self._validate(picking, tracking=TRACKING[:1])
        send.assert_not_called()
        self.assertIn("Costco warehouse ID", self._confirmation(picking).exchange_error)

    def test_the_costco_warehouse_id_is_on_the_warehouse_form(self):
        arch = self.env["stock.warehouse"].get_view(view_type="form")["arch"]
        self.assertIn('name="costco_warehouse_code"', arch)

    def test_the_boxes_of_an_item_follow_the_order_the_carrier_labels_them(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [2, 1])
        labelled = self.carrier._get_packages_from_picking(
            picking, self.env["stock.package.type"]
        )
        self._validate(picking)
        text = self._text(self._confirmation(picking))
        self.assertEqual(re.findall(r"MAN\*CP\*(\w+)~", text), list(TRACKING))
        self.assertEqual(len(labelled), len(TRACKING))

    def test_one_unit_split_over_two_packages_lists_both_boxes(self):
        self._storable("PLAIN-1")
        __, picking = self._order(kits=1, sku="PLAIN-1")
        packages = [
            self.env["stock.package"].create({"shipping_weight": 5.0}) for __ in (0, 1)
        ]
        move = picking.move_ids
        move.move_line_ids.unlink()
        for package in packages:
            vals = move._prepare_move_line_vals(quantity=0.5)
            vals["result_package_id"] = package.id
            self.env["stock.move.line"].create(vals)
        move.picked = True
        self._validate(picking)
        self.assertEqual(picking.state, "done")
        record = self._confirmation(picking)
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._text(record)
        self.assertEqual(text.count("LIN*"), 1)
        self.assertIn("SN1**1*EA*****AC~", text)
        self.assertEqual(re.findall(r"MAN\*CP\*(\w+)~", text), list(TRACKING))

    def _user(self, *xmlids):
        return self.env["res.users"].create(
            {
                "name": "Ordinary user",
                "login": f"ordinary_{'_'.join(xmlids)}",
                "group_ids": [(6, 0, [self.env.ref(x).id for x in xmlids])],
            }
        )

    def test_a_warehouse_user_validating_the_delivery_still_sends_it(self):
        # No access to invoices or to the storage: the message is built and sent
        # as a system task, so the person who validates does not matter.
        user = self._user("stock.group_stock_user")
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        picking.write(
            {"carrier_id": self.carrier.id, "carrier_tracking_ref": TRACKING[0]}
        )
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            picking.with_user(user).with_context(
                skip_immediate=True, skip_backorder=True
            ).button_validate()
        send.assert_called_once()
        self.assertFalse(self._confirmation(picking).exchange_error)
