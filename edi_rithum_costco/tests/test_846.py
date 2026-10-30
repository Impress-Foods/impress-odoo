"""Inventory advice (846): written from stock, checked by the Costco map."""

from __future__ import annotations

import dataclasses
import unittest
from datetime import date, datetime

from odoo.addons.edi_x12.x12 import outbound, simple_xml
from odoo.addons.edi_x12.x12.engine import validate_document
from odoo.addons.edi_x12.x12.simple_xml import walk_loops

from ..documents import tset_846
from .maps import MAP_PATH

try:
    from odoo.tests.common import BaseCase as TestCaseBase
except ImportError:  # pragma: no cover - standalone run
    TestCaseBase = unittest.TestCase

if "test_tags" not in vars(TestCaseBase):
    TestCaseBase.test_tags = {"standard", "at_install"}

ENVELOPE = outbound.Envelope(
    sender_id="OURID",
    receiver_id="THEIRID",
    control_number=5,
    production=False,
    sent_at=datetime(2026, 10, 30, 9, 0),
    interchange_version="00401",
    functional_version="004010",
    functional_id="IB",
)


def _stock(warehouse: str, quantity: int) -> tset_846.WarehouseStock:
    return tset_846.WarehouseStock(warehouse, quantity)


def _advice(**changes) -> tset_846.InventoryAdvice:
    advice = tset_846.InventoryAdvice(
        report_number="20261030090000",
        created_on=date(2026, 10, 30),
        merchant="COSTCO",
        items=(
            tset_846.InventoryItem(
                "88880601",
                "99990601",
                "Gift box",
                (_stock("2001", 30), _stock("2002", 12)),
            ),
            tset_846.InventoryItem(
                "88880602",
                "99990602",
                "Old box",
                (_stock("2001", 0),),
                discontinued_on=date(2026, 12, 31),
            ),
        ),
    )
    return dataclasses.replace(advice, **changes)


def _render(advice: tset_846.InventoryAdvice) -> str:
    tree = outbound.interchange(ENVELOPE, tset_846.build_body(advice), "846", "0001")
    return outbound.render(tree, MAP_PATH)


class TestInventoryAdvice(TestCaseBase):
    def _valid(self, text: str):
        outcome = validate_document(text, MAP_PATH)
        self.assertTrue(outcome.ok, outcome.issues)
        (st_loop,) = walk_loops(simple_xml.parse(outcome.xml), "ST_LOOP")
        return st_loop

    def test_the_header_and_totals(self):
        text = _render(_advice())
        self._valid(text)
        self.assertIn("GS*IB*", text)
        self.assertIn("BIA*00*SI*20261030090000*20261030~", text)
        self.assertIn("REF*IO*COSTCO~", text)
        self.assertIn("CTT*2~", text)

    def test_an_item_reports_its_total_and_each_warehouse(self):
        text = _render(_advice())
        self._valid(text)
        self.assertIn("LIN**VN*88880601*SK*99990601~", text)
        self.assertIn("PID*F*08***Gift box~", text)
        self.assertIn("QTY*61*42*EA~", text)
        self.assertIn("LS*REF~\nREF*WS*2001*30~\nREF*WS*2002*12~\nLE*REF~", text)

    def test_a_discontinued_item_carries_its_date(self):
        text = _render(_advice())
        self.assertIn("DTM*036*20261231~", text)
        self.assertEqual(text.count("DTM*036"), 1)

    def test_an_out_of_stock_item_is_still_reported(self):
        text = _render(_advice())
        self.assertIn("QTY*61*0*EA~", text)
        self.assertIn("REF*WS*2001*0~", text)

    def test_the_total_always_equals_the_sum_of_the_warehouses(self):
        st = self._valid(_render(_advice()))
        for item in walk_loops(st, "LIN_LOOP"):
            total = int(item.segment("QTY").value("QTY02"))
            parts = [
                int(loop.segment("REF").value("REF03"))
                for loop in walk_loops(item, "REF_LOOP")
            ]
            self.assertEqual(total, sum(parts))

    def test_a_missing_value_is_refused_before_anything_is_sent(self):
        item = _advice().items[0]
        cases = {
            "report_number": {"report_number": ""},
            "merchant": {"merchant": ""},
            "items": {"items": ()},
            "vendor_sku": {"items": (dataclasses.replace(item, vendor_sku=""),)},
            "buyer_sku": {"items": (dataclasses.replace(item, buyer_sku=""),)},
            "description": {"items": (dataclasses.replace(item, description=""),)},
            "stock": {"items": (dataclasses.replace(item, stock=()),)},
            "warehouse": {
                "items": (dataclasses.replace(item, stock=(_stock("", 1),)),)
            },
            "non-negative": {
                "items": (dataclasses.replace(item, stock=(_stock("2001", -1),)),)
            },
        }
        for name, changes in cases.items():
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, name):
                tset_846.build_body(_advice(**changes))

    def test_a_long_description_is_cut_to_what_the_element_allows(self):
        item = dataclasses.replace(_advice().items[0], description="x" * 120)
        text = _render(_advice(items=(item,)))
        self._valid(text)
        self.assertIn("PID*F*08***" + "x" * 80 + "~", text)

    def test_the_map_itself_refuses_an_unknown_quantity_qualifier(self):
        text = _render(_advice()).replace("QTY*61*", "QTY*99*", 1)
        self.assertFalse(validate_document(text, MAP_PATH).ok)

    def test_the_map_itself_refuses_a_missing_description(self):
        text = _render(_advice())
        text = "\n".join(
            line for line in text.split("\n") if not line.startswith("PID*")
        )
        self.assertFalse(validate_document(text, MAP_PATH).ok)
