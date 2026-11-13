"""Units Costco is owed are never dropped without telling it."""

from odoo.exceptions import UserError
from odoo.tools import mute_logger

from .common import TRACKING, CostcoShipmentCase
from .test_flow_850 import _order_text


class TestGuards(CostcoShipmentCase):
    def _no_backorder(self, picking):
        picking.write(
            {"carrier_id": self.carrier.id, "carrier_tracking_ref": TRACKING[0]}
        )
        return picking.with_context(
            skip_immediate=True,
            skip_backorder=True,
            picking_ids_not_to_backorder=picking.ids,
        ).button_validate()

    def _cancel_with_costco(self, order, quantity):
        action = order.action_costco_cancel()
        context = action["context"]
        cancellation = self.env["edi.rithum.costco.cancellation"].create(
            {
                "order_id": order.id,
                "reason_id": self.env.ref(
                    "edi_rithum_costco.cancel_reason_out_of_stock"
                ).id,
                "line_ids": context["default_line_ids"],
            }
        )
        cancellation.line_ids.quantity = quantity
        cancellation.action_confirm()

    def test_an_imported_order_is_confirmed_without_telling_the_customer(self):
        text = _order_text(po_number="PO-CONFIRMED", vendor_sku="KIT-1")
        record = self.backend.create_record(
            "costco_850_in",
            {
                "exchange_file": self._b64(text),
                "rithum_partner_id": self.env.ref(
                    "edi_rithum_costco.rithum_partner_costco"
                ).id,
            },
        )
        self.env["edi.rithum.costco.mapping.850"].process(record)
        order = self.env["sale.order"].search(
            [("client_order_ref", "=", "PO-CONFIRMED")]
        )
        self.assertEqual(order.state, "sale")
        self.assertTrue(order.picking_ids)
        self.assertFalse(
            self.env["mail.mail"].search(
                [("model", "=", "sale.order"), ("res_id", "=", order.id)]
            )
        )

    def test_no_backorder_is_refused_while_costco_is_owed_units(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [2])
        with self.assertRaisesRegex(UserError, "Cancel them with Costco"):
            self._no_backorder(picking)
        self.assertNotEqual(picking.state, "done")

    def test_no_backorder_passes_once_the_units_are_cancelled_with_costco(self):
        order, picking = self._order(kits=3)
        self._cancel_with_costco(order, 1)
        self._pack(picking, [2])
        self._no_backorder(picking)
        self.assertEqual(picking.state, "done")
        self.assertEqual(order.order_line.product_uom_qty, 2)

    def test_no_backorder_is_fine_when_everything_ships(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._no_backorder(picking)
        self.assertEqual(picking.state, "done")

    def test_a_delivery_with_open_costco_lines_cannot_be_cancelled(self):
        __, picking = self._order(kits=3)
        with self.assertRaisesRegex(UserError, "Cancel with Costco"):
            picking.action_cancel()
        self.assertNotEqual(picking.state, "cancel")

    def test_a_backorder_cannot_be_cancelled_but_costco_can_cancel_it(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [2])
        self._validate(picking, tracking=TRACKING[:1])
        backorder = order.picking_ids - picking
        with self.assertRaises(UserError):
            backorder.action_cancel()
        self._cancel_with_costco(order, 1)
        self.assertEqual(backorder.state, "cancel")

    def test_a_delivery_of_another_order_cancels_normally(self):
        __, picking = self._order(kits=3, from_edi=False)
        picking.action_cancel()
        self.assertEqual(picking.state, "cancel")

    def test_a_costco_order_set_back_to_draft_is_still_guarded(self):
        order, __ = self._order(kits=3)
        order.state = "draft"
        self.assertTrue(order.costco_can_cancel)
        with self.assertRaisesRegex(UserError, "Cancel with Costco"):
            order.action_cancel()

    def test_a_costco_order_cannot_be_deleted(self):
        order, __ = self._order(kits=3)
        order.state = "draft"
        with (
            self.assertRaisesRegex(UserError, "cannot be deleted"),
            mute_logger("odoo.sql_db"),
        ):
            order.unlink()

    def test_an_order_of_another_origin_is_deleted_normally(self):
        order, __ = self._order(kits=3, from_edi=False)
        order.action_cancel()
        order.unlink()
        self.assertFalse(order.exists())

    def _b64(self, text):
        import base64

        return base64.b64encode(text.encode("cp1252"))
