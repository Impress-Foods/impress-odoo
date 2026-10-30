"""Inbound 850: a validated purchase order reads into records."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal

from odoo.addons.edi_x12.x12 import outbound, simple_xml
from odoo.addons.edi_x12.x12.engine import validate_document
from odoo.addons.edi_x12.x12.party import Party
from odoo.addons.edi_x12.x12.simple_xml import Loop, Segment

from ..documents import tset_850
from .maps import MAP_PATH

try:
    from odoo.tests.common import BaseCase as TestCaseBase
except ImportError:  # pragma: no cover - standalone run
    TestCaseBase = unittest.TestCase

if "test_tags" not in vars(TestCaseBase):
    TestCaseBase.test_tags = {"standard", "at_install"}


def _order_text() -> str:
    body = Loop(
        "BODY",
        [
            Segment(
                "BEG",
                {"BEG01": "00", "BEG02": "SA", "BEG03": "PO-7741", "BEG05": "20200310"},
            ),
            Segment("REF", {"REF01": "IA", "REF02": "3286495"}),
            Segment(
                "TD5",
                {
                    "TD501": "Z",
                    "TD502": "ZZ",
                    "TD503": "UPS",
                    "TD504": "ZZ",
                    "TD505": "Ground",
                },
            ),
            Loop(
                "N1_LOOP",
                [
                    Segment(
                        "N1",
                        {
                            "N101": "ST",
                            "N102": "SHIP TO",
                            "N103": "ZZ",
                            "N104": "0001234567890",
                        },
                    ),
                    Segment("N3", {"N301": "1 MAIN ST"}),
                    Segment(
                        "N4",
                        {
                            "N401": "ANYTOWN",
                            "N402": "AK",
                            "N403": "99501",
                            "N404": "US",
                        },
                    ),
                ],
            ),
            Loop(
                "PO1_LOOP",
                [
                    Segment(
                        "PO1",
                        {
                            "PO101": "0001",
                            "PO102": "2",
                            "PO103": "EA",
                            "PO104": "5.5",
                            "PO106": "SK",
                            "PO107": "999999",
                            "PO108": "UP",
                            "PO109": "123456789012",
                        },
                    ),
                ],
            ),
            Segment("CTT", {"CTT01": "1"}),
        ],
    )
    envelope = outbound.Envelope(
        sender_id="COSTCOTEST00001",
        receiver_id="DSCO",
        control_number=7,
        production=False,
        sent_at=datetime(2020, 3, 10, 9, 0),
        interchange_version="00401",
        functional_version="004010",
        functional_id="PO",
    )
    return outbound.render(
        outbound.interchange(envelope, body, "850", "0001"), MAP_PATH
    )


class TestInbound850(TestCaseBase):
    def _read(self):
        outcome = validate_document(_order_text(), MAP_PATH)
        self.assertTrue(outcome.ok)
        return tset_850.read_purchase_orders(simple_xml.parse(outcome.xml))

    def test_header_is_read(self):
        (order,) = self._read()
        self.assertEqual(order.purpose, "00")
        self.assertEqual(order.order_type, "SA")
        self.assertEqual(order.po_number, "PO-7741")
        self.assertEqual(order.created_on, date(2020, 3, 10))

    def test_ship_to_is_read(self):
        (order,) = self._read()
        self.assertEqual(
            order.ship_to,
            Party(
                name="SHIP TO",
                address="1 MAIN ST",
                city="ANYTOWN",
                state="AK",
                postal_code="99501",
                country="US",
            ),
        )

    def test_line_is_read_with_identifiers(self):
        (order,) = self._read()
        (line,) = order.lines
        self.assertEqual(line.line_number, "0001")
        self.assertEqual(line.quantity, Decimal(2))
        self.assertEqual(line.unit, "EA")
        self.assertEqual(line.unit_price, Decimal("5.5"))
        self.assertEqual(line.sku, "999999")
        self.assertEqual(line.identifiers, {"UP": "123456789012"})


class TestInbound850Pure(TestCaseBase):
    def test_a_po1_without_sku_qualifier_is_refused(self):
        body = Loop(
            "ST_LOOP",
            [
                Segment("ST", {"ST01": "850", "ST02": "0001"}),
                Segment(
                    "BEG",
                    {"BEG01": "00", "BEG02": "SA", "BEG03": "P", "BEG05": "20200310"},
                ),
                Loop(
                    "PO1_LOOP",
                    [
                        Segment(
                            "PO1",
                            {
                                "PO101": "1",
                                "PO102": "1",
                                "PO103": "EA",
                                "PO104": "1",
                                "PO106": "UP",
                                "PO107": "x",
                            },
                        )
                    ],
                ),
            ],
        )
        with self.assertRaises(ValueError):
            tset_850.read_purchase_orders(Loop("x12simple", [body]))
