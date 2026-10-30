"""Shipment confirmations (856): written from a shipment, checked by the Costco map."""

from __future__ import annotations

import dataclasses
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from odoo.addons.edi_x12.x12 import outbound, simple_xml
from odoo.addons.edi_x12.x12.engine import validate_document
from odoo.addons.edi_x12.x12.fields import time_code
from odoo.addons.edi_x12.x12.simple_xml import walk_loops

from ..documents import tset_856
from .maps import MAP_PATH

try:
    from odoo.tests.common import BaseCase as TestCaseBase
except ImportError:  # pragma: no cover - standalone run
    TestCaseBase = unittest.TestCase

if "test_tags" not in vars(TestCaseBase):
    TestCaseBase.test_tags = {"standard", "at_install"}

EST = timezone(timedelta(hours=-5))
TRACK_A, TRACK_B = "1Z999AA10123456784", "1Z999AA10123456792"
ENVELOPE = outbound.Envelope(
    sender_id="OURID",
    receiver_id="THEIRID",
    control_number=3,
    production=False,
    sent_at=datetime(2026, 10, 29, 16, 45),
    interchange_version="00401",
    functional_version="004010",
    functional_id="SH",
)


def _item(
    line: str, vendor: str, buyer: str, quantity: str, *tracking: str
) -> tset_856.ShippedItem:
    return tset_856.ShippedItem(line, vendor, buyer, Decimal(quantity), tracking)


def _cancel(
    line: str, quantity: str, reason: str = "out_of_stock", note: str = ""
) -> tset_856.CancelledItem:
    return tset_856.CancelledItem(
        line, "8888" + line, "9999" + line, Decimal(quantity), reason, note
    )


def _confirmation(**changes) -> tset_856.ShipmentConfirmation:
    confirmation = tset_856.ShipmentConfirmation(
        shipment_id="WH/OUT/00001",
        po_number="00000100000001",
        created_at=datetime(2026, 10, 29, 16, 45, tzinfo=EST),
        shipped=(
            _item(
                "1",
                "88880601",
                "99990601",
                "5",
                "1Z999AA10123456784",
                "1Z999AA10123456792",
            ),
            _item("2", "88880602", "99990602", "1", TRACK_A),
        ),
        invoice_number="INV/2026/0001",
        shipping_method="UPSN_CG",
        weight=Decimal("10.5"),
        warehouse="2001",
        shipped_at=datetime(2026, 10, 29, 16, 30, tzinfo=EST),
    )
    return dataclasses.replace(confirmation, **changes)


def _render(confirmation: tset_856.ShipmentConfirmation) -> str:
    tree = outbound.interchange(
        ENVELOPE, tset_856.build_body(confirmation), "856", "0001"
    )
    return outbound.render(tree, MAP_PATH)


class TestShipmentConfirmation(TestCaseBase):
    def _st_loop(self, text: str) -> simple_xml.Loop:
        outcome = validate_document(text, MAP_PATH)
        self.assertTrue(outcome.ok, outcome.issues)
        (st_loop,) = walk_loops(simple_xml.parse(outcome.xml), "ST_LOOP")
        return st_loop

    def test_the_header_and_shipment_carry_what_costco_requires(self):
        text = _render(_confirmation())
        st = self._st_loop(text)
        bsn = st.segment("BSN")
        self.assertEqual(
            [bsn.value(f"BSN0{i}") for i in range(1, 6)],
            ["00", "WH/OUT/00001", "20261029", "1645", "0002"],
        )
        (shipment,) = st.loops("HL_S_LOOP")
        td1 = shipment.segment("TD1")
        self.assertEqual(
            [td1.value("TD106"), td1.value("TD107"), td1.value("TD108")],
            ["A3", "10.5", "01"],
        )
        td5 = shipment.segment("TD5")
        self.assertEqual((td5.value("TD501"), td5.value("TD505")), ("B", "UPSN_CG"))
        self.assertIn("DTM*011*20261029*1630*20~", text)

    def test_the_levels_nest_as_standard_carton(self):
        st = self._st_loop(_render(_confirmation()))
        hierarchy = []
        for level in ("HL_S_LOOP", "HL_O_LOOP", "HL_I_LOOP", "HL_P_LOOP"):
            for loop in walk_loops(st, level):
                hl = loop.segment("HL")
                hierarchy.append(
                    (int(hl.value("HL01")), hl.value("HL02"), hl.value("HL03"))
                )
        self.assertEqual(
            sorted(hierarchy),
            [
                (1, None, "S"),
                (2, "1", "O"),
                (3, "2", "I"),
                (4, "3", "P"),
                (5, "3", "P"),
                (6, "2", "I"),
                (7, "6", "P"),
            ],
        )

    def test_the_order_item_and_pack_values(self):
        st = self._st_loop(_render(_confirmation()))
        (order,) = walk_loops(st, "HL_O_LOOP")
        self.assertEqual(order.segment("PRF").value("PRF01"), "00000100000001")
        ref = order.segment("REF")
        self.assertEqual(
            (ref.value("REF01"), ref.value("REF02")), ("IV", "INV/2026/0001")
        )
        first, _second = order.loops("HL_I_LOOP")
        lin, sn1 = first.segment("LIN"), first.segment("SN1")
        self.assertEqual(
            [lin.value(f"LIN0{i}") for i in range(1, 6)],
            ["1", "VN", "88880601", "SK", "99990601"],
        )
        self.assertEqual(
            [sn1.value("SN102"), sn1.value("SN103"), sn1.value("SN108")],
            ["5", "EA", "AC"],
        )
        boxes = [
            pack.segment("MAN").value("MAN02") for pack in first.loops("HL_P_LOOP")
        ]
        self.assertEqual(boxes, ["1Z999AA10123456784", "1Z999AA10123456792"])

    def test_a_cancellation_alone_needs_no_shipping_details(self):
        text = _render(
            tset_856.ShipmentConfirmation(
                shipment_id="CANCEL-1",
                po_number="00000100000001",
                created_at=datetime(2026, 10, 29, 16, 45, tzinfo=EST),
                cancelled=(_cancel("1", "3", "bad_sku", "no such sku"),),
            )
        )
        self._st_loop(text)
        self.assertIn("SN1**0*EA**3*EA**ID~", text)
        self.assertIn("REF*TD*bad_sku*no such sku~", text)
        for name in ("TD1", "TD5", "DTM", "N1", "MAN", "REF*IV"):
            self.assertNotIn(f"\n{name}*", text)

    def test_a_line_partly_shipped_and_partly_cancelled_takes_two_items(self):
        text = _render(
            _confirmation(
                shipped=(
                    _item("1", "88880601", "99990601", "2", "1Z999AA10123456784"),
                ),
                cancelled=(_cancel("1", "3", "out_of_stock"),),
            )
        )
        st = self._st_loop(text)
        statuses = [
            item.segment("SN1").value("SN108") for item in walk_loops(st, "HL_I_LOOP")
        ]
        self.assertEqual(statuses, ["AC", "ID"])

    def test_a_missing_value_is_refused_before_anything_is_sent(self):
        item = _confirmation().shipped[0]
        cases = {
            "shipment_id": {"shipment_id": ""},
            "po_number": {"po_number": ""},
            "invoice_number": {"invoice_number": ""},
            "shipping_method": {"shipping_method": ""},
            "weight": {"weight": Decimal(0)},
            "warehouse": {"warehouse": ""},
            "shipped_at": {"shipped_at": None},
            "items": {"shipped": ()},
            "tracking_number": {
                "shipped": (dataclasses.replace(item, tracking_numbers=()),)
            },
            "quantity": {"shipped": (dataclasses.replace(item, quantity=Decimal(0)),)},
            "buyer_sku": {"shipped": (dataclasses.replace(item, buyer_sku=""),)},
            "reason": {
                "shipped": (),
                "cancelled": (_cancel("1", "1", ""),),
            },
        }
        for name, changes in cases.items():
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, name):
                tset_856.build_body(_confirmation(**changes))

    def test_the_map_itself_refuses_the_pick_pack_structure_code(self):
        text = _render(_confirmation()).replace("*0002~", "*0001~")
        outcome = validate_document(text, MAP_PATH)
        self.assertFalse(outcome.ok)

    def test_the_map_itself_refuses_an_unknown_item_status(self):
        text = _render(_confirmation()).replace("*EA*****AC~", "*EA*****XX~")
        outcome = validate_document(text, MAP_PATH)
        self.assertFalse(outcome.ok)

    def test_the_time_codes_match_those_in_the_costco_850_samples(self):
        # Every code in the samples is one of ours for some UTC offset.
        ours = {
            time_code(datetime(2026, 10, 29, tzinfo=timezone(timedelta(hours=h))))
            for h in range(-12, 13)
        }
        self.assertLessEqual({"20", "21"}, ours)

    def test_every_shipped_item_names_the_warehouse_it_shipped_from(self):
        st = self._st_loop(_render(_confirmation()))
        items = list(walk_loops(st, "HL_I_LOOP"))
        self.assertEqual(len(items), 2)
        for item in items:
            (name_loop,) = item.loops("N1_LOOP")
            n1 = name_loop.segment("N1")
            self.assertEqual(
                [n1.value("N101"), n1.value("N103"), n1.value("N104")],
                ["WH", "54", "2001"],
            )
