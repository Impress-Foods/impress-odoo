"""Costco 850 compliance: the partner's sample interchanges must pass as they are.

The samples are the acceptance test, so their content is read at run time and
never copied into the repository. Set EDI_X12_COMPLIANCE_DIR to the folder that
holds the ``*.intchg`` samples; without it the tests are skipped.
"""

import os
import unittest
from datetime import datetime
from pathlib import Path

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edi_x12.x12 import outbound, simple_xml, tset_997
from odoo.addons.edi_x12.x12.engine import SEVERITY_ERROR, validate_document

from ..documents import tset_850
from .maps import MAP_PATH

SCHEME = "X12"
SAMPLE_DIR = Path(os.environ.get("EDI_X12_COMPLIANCE_DIR", ""))
SAMPLES = sorted(SAMPLE_DIR.glob("*.intchg")) if SAMPLE_DIR.is_dir() else []


def _sender(text: str) -> str:
    """ISA06, without the padding the envelope adds to it."""
    return text.split("*")[6].strip()


@unittest.skipUnless(SAMPLES, "EDI_X12_COMPLIANCE_DIR has no *.intchg samples")
class TestCostcoSamples850(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mapping = cls.env["edi.rithum.costco.mapping.850"]
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.unit.unece_code = "C62"
        cls.texts = {path.name: path.read_bytes().decode("cp1252") for path in SAMPLES}
        cls.outcomes = {
            name: validate_document(text, MAP_PATH) for name, text in cls.texts.items()
        }
        cls.scheme = cls.env.ref("edi_x12.id_category_x12")
        for sender in {_sender(text) for text in cls.texts.values()}:
            cls._create_partner(sender)
        for name in cls.texts:
            for purchase_order in cls._purchase_orders(name):
                for line in purchase_order.lines:
                    cls._create_product(line.identifiers["VN"])

    @classmethod
    def _create_partner(cls, sender: str) -> None:
        partner = cls.env["res.partner"].create({"name": f"Sample {sender}"})
        cls.env["res.partner.id_number"].create(
            {"partner_id": partner.id, "category_id": cls.scheme.id, "name": sender}
        )

    @classmethod
    def _create_product(cls, sku: str) -> None:
        if not cls.env["product.product"].search([("default_code", "=", sku)]):
            cls.env["product.product"].create({"name": sku, "default_code": sku})

    @classmethod
    def _purchase_orders(cls, name: str) -> list:
        root = simple_xml.parse(cls.outcomes[name].xml)
        return tset_850.read_purchase_orders(root)

    def test_every_sample_passes_validation(self):
        for name, outcome in self.outcomes.items():
            with self.subTest(sample=name):
                errors = [i for i in outcome.issues if i.severity == SEVERITY_ERROR]
                self.assertTrue(outcome.ok, f"{name}: {errors}")
                self.assertIsNotNone(outcome.xml)

    def test_every_po_becomes_one_order_with_its_lines(self):
        for name in self.texts:
            text = self.texts[name]
            purchase_orders = self._purchase_orders(name)
            with self.subTest(sample=name):
                orders = self.mapping.create_orders(text, SCHEME, MAP_PATH)
                self.assertEqual(len(orders), len(purchase_orders))
                by_ref = {order.client_order_ref: order for order in orders}
                for purchase_order in purchase_orders:
                    self._assert_order_matches(
                        by_ref[purchase_order.po_number], purchase_order
                    )

    def _assert_order_matches(self, order, purchase_order) -> None:
        self.assertEqual(len(order.order_line), len(purchase_order.lines))
        for line, sample in zip(order.order_line, purchase_order.lines, strict=True):
            self.assertEqual(line.product_id.default_code, sample.identifiers["VN"])
            self.assertEqual(line.product_uom_id, self.unit)
            self.assertEqual(line.product_uom_qty, float(sample.quantity))
            self.assertEqual(line.price_unit, float(sample.unit_price))
            self.assertEqual(line.edi_id, sample.line_number)
            if sample.description:
                self.assertEqual(line.name, sample.description)
        if purchase_order.ship_to is not None:
            self.assertEqual(order.partner_shipping_id.parent_id, order.partner_id)

    def test_sending_a_sample_twice_is_refused(self):
        text = next(iter(self.texts.values()))
        self.mapping.create_orders(text, SCHEME, MAP_PATH)
        with self.assertRaises(UserError):
            self.mapping.create_orders(text, SCHEME, MAP_PATH)

    def test_every_sample_is_acknowledged_with_a_status_for_each_po(self):
        envelope = outbound.Envelope(
            sender_id="OURID",
            receiver_id="THEIRID",
            control_number=1,
            production=False,
            sent_at=datetime(2026, 10, 29, 12, 0),
            interchange_version="00401",
            functional_version="004010",
            functional_id="FA",
        )
        for name, text in self.texts.items():
            with self.subTest(sample=name):
                ack_text = tset_997.acknowledge(
                    text, self.outcomes[name], envelope, MAP_PATH
                )
                root = simple_xml.parse(validate_document(ack_text, MAP_PATH).xml)
                (ack,) = tset_997.read_functional_acknowledgments(root)
                self.assertEqual(ack.status, tset_997.ACCEPTED)
                self.assertEqual(
                    [t.control_number for t in ack.transactions],
                    [
                        f"{n:04d}"
                        for n in range(1, len(self._purchase_orders(name)) + 1)
                    ],
                )
