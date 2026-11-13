"""A Costco delivery validated in part tells Costco what is backordered."""

import re
from datetime import timedelta

from odoo import fields

from .common import TRACKING, CostcoShipmentCase

NOTICE = "costco_backorder_out"
SHIPMENT = "costco_856_out"


class TestBackorder(CostcoShipmentCase):
    def _partial(self, kits=3, shipped=2, from_edi=True):
        """An order delivered in part; the order, delivery and backorder."""
        order, picking = self._order(kits=kits, from_edi=from_edi)
        self._pack(picking, [shipped])
        self._validate(picking, tracking=TRACKING[:1])
        return order, picking, order.picking_ids - picking

    def _records(self, picking, code):
        return picking.exchange_record_ids.filtered(lambda r: r.type_id.code == code)

    def _notice(self, backorder):
        return self._text(self._records(backorder, NOTICE))

    def test_a_partial_delivery_backorders_the_rest_with_costco(self):
        __, picking, backorder = self._partial()
        self.assertEqual(picking.state, "done")
        (record,) = self._records(backorder, NOTICE)
        self.assertFalse(record.exchange_error, record.exchange_error)
        text = self._text(record)
        self.assertIn("SN1**0*EA**1*EA**IB~", text)
        for absent in ("TD1*", "TD5*", "N1*", "MAN*", "REF*IV", "DTM*011"):
            self.assertNotIn(f"\n{absent}", text)

    def test_the_units_are_promised_five_days_from_today(self):
        __, __, backorder = self._partial()
        expected = fields.Date.context_today(backorder) + timedelta(days=5)
        pattern = rf"\nDTM\*079\*{expected:%Y%m%d}\*0000\*(UT|\d\d)~"
        self.assertRegex(self._notice(backorder), pattern)

    def test_the_backorder_is_sent_before_the_shipment_confirmation(self):
        __, picking, backorder = self._partial()
        notice = self._records(backorder, NOTICE)
        shipment = self._records(picking, SHIPMENT)
        self.assertLess(notice.id, shipment.id)
        self.assertLess(
            int(notice.x12_control_number), int(shipment.x12_control_number)
        )

    def test_the_notice_has_its_own_shipment_id(self):
        __, picking, backorder = self._partial()
        ids = re.findall(r"\nBSN\*00\*([^*]+)\*", self._notice(backorder))
        self.assertEqual(ids, [f"{backorder.name}-BO"])
        # the delivery's own confirmation keeps the delivery's name
        self.assertIn(
            f"BSN*00*{picking.name}*", self._text(self._records(picking, SHIPMENT))
        )

    def test_a_delivery_that_is_not_costcos_sends_no_notice(self):
        __, __, backorder = self._partial(from_edi=False)
        self.assertTrue(backorder)
        self.assertFalse(backorder.exchange_record_ids)

    def test_a_complete_delivery_has_no_backorder_to_announce(self):
        order, picking = self._order(kits=3)
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1])
        self.assertEqual(order.picking_ids, picking)
        self.assertFalse(self._records(picking, NOTICE))

    def test_a_notice_that_cannot_be_sent_does_not_block_the_delivery(self):
        order, picking = self._order(kits=3)
        # without its file, the order is addressed from its retailer's settings
        order.origin_exchange_record_id.exchange_file = False
        order.rithum_partner_id.x12_id = False
        self._pack(picking, [2])
        self._validate(picking, tracking=TRACKING[:1])
        backorder = order.picking_ids - picking
        self.assertEqual(picking.state, "done")
        (record,) = self._records(backorder, NOTICE)
        self.assertIn("Set the interchange ID", record.exchange_error)
        chatter = " ".join(backorder.message_ids.mapped("body"))
        self.assertIn("could not be sent", chatter)

    def test_the_backorder_still_ships_with_its_own_confirmation(self):
        order, picking, backorder = self._partial()
        self._pack(backorder, [1])
        self._validate(backorder, tracking=TRACKING[1:])
        self.assertEqual(backorder.state, "done")
        confirmation = self._records(backorder, SHIPMENT)
        self.assertIn(f"BSN*00*{backorder.name}*", self._text(confirmation))
        self.assertEqual(len(self._records(backorder, NOTICE)), 1)
        self.assertEqual(order.picking_ids, picking | backorder)
