"""A Costco file of several 850s: each purchase order is handled on its own."""

import base64
from unittest import mock

from odoo.tests.common import TransactionCase

from odoo.addons.edi_x12.x12.reading import segments

from .test_flow_850 import SENDER, _order_text

OUR_ID = "OURID"
TERMINATOR = "~\r\n"


def _one_file(*texts: str) -> str:
    """The purchase orders of several single-order files, in one interchange."""
    isa, gs = segments(texts[0])[:2]
    body = []
    for number, text in enumerate(texts, start=1):
        order = [
            seg for seg in segments(text) if seg[0] not in ("ISA", "GS", "GE", "IEA")
        ]
        order[0][2] = order[-1][2] = f"{number:04d}"
        body += order
    parts = [isa, gs, *body, ["GE", str(len(texts)), gs[6]], ["IEA", "1", isa[13]]]
    return "".join("*".join(part) + TERMINATOR for part in parts)


class TestSplit850(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, queue_job__no_delay=True))
        cls.backend = cls.env.ref("edi_rithum.rithum_backend")
        cls.backend.write({"x12_sender_id": OUR_ID})
        cls.env.ref("edi_rithum_costco.rithum_partner_costco").x12_id = SENDER
        scheme = cls.env.ref("edi_x12.id_category_x12")
        partner = cls.env["res.partner"].create({"name": "Retail Customer"})
        cls.env["res.partner.id_number"].create(
            {"partner_id": partner.id, "category_id": scheme.id, "name": SENDER}
        )
        cls.env["product.product"].create({"name": "Widget", "default_code": "999999"})
        cls.env.ref("uom.product_uom_unit").unece_code = "C62"

    def _receive(self, *orders: str):
        text = _one_file(*orders)
        record = self.backend.create_record(
            "rithum_in",
            {
                "exchange_file": base64.b64encode(text.encode("cp1252")),
                "edi_exchange_state": "input_received",
            },
        )
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            record.action_exchange_process()
        return record

    def _children(self, record):
        return self.env["edi.exchange.record"].search([("parent_id", "=", record.id)])

    def _orders(self, *numbers: str):
        return self.env["sale.order"].search([("client_order_ref", "in", numbers)])

    def _file_with_an_unknown_product(self):
        return self._receive(
            _order_text(po_number="PO-A"),
            _order_text(po_number="PO-B", vendor_sku="NOPE"),
            _order_text(po_number="PO-C"),
        )

    def test_each_order_of_the_file_gets_a_record_and_an_order(self):
        record = self._receive(
            _order_text(po_number="PO-A"), _order_text(po_number="PO-C")
        )
        self.assertEqual(record.edi_exchange_state, "input_processed")
        children = self._children(record).filtered(
            lambda r: r.type_id.code == "costco_850_in"
        )
        self.assertEqual(len(children), 2)
        orders = self._orders("PO-A", "PO-C")
        self.assertEqual(orders.origin_exchange_record_id, children)
        self.assertTrue(all(order._costco_is_order() for order in orders))

    def test_one_bad_order_does_not_stop_the_others(self):
        record = self._file_with_an_unknown_product()
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertEqual(len(self._orders("PO-A", "PO-C")), 2)
        self.assertFalse(self._orders("PO-B"))
        (failed,) = self._children(record).filtered(
            lambda r: r.edi_exchange_state == "input_processed_error"
        )
        self.assertIn("NOPE", failed.exchange_error)

    def test_fixing_the_product_and_retrying_creates_the_missing_order(self):
        record = self._file_with_an_unknown_product()
        self.env["product.product"].create({"name": "Gadget", "default_code": "NOPE"})
        (failed,) = self._children(record).filtered(
            lambda r: r.edi_exchange_state == "input_processed_error"
        )
        failed.action_retry()
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            failed.action_exchange_process()
        self.assertEqual(failed.edi_exchange_state, "input_processed")
        self.assertEqual(len(self._orders("PO-A", "PO-B", "PO-C")), 3)

    def test_the_file_is_acknowledged_once_and_not_the_orders(self):
        record = self._file_with_an_unknown_product()
        acks = self._children(record).filtered(
            lambda r: r.type_id.code != "costco_850_in"
        )
        self.assertEqual(acks, record.ack_exchange_id)
        for child in self._children(record) - acks:
            self.assertFalse(child.ack_exchange_id)
            self.assertFalse(self._children(child))

    def test_a_resent_file_creates_only_the_new_orders(self):
        self._receive(_order_text(po_number="PO-A"), _order_text(po_number="PO-B"))
        again = self._receive(
            _order_text(po_number="PO-A"), _order_text(po_number="PO-C")
        )
        self.assertEqual(len(self._orders("PO-A")), 1)
        self.assertEqual(len(self._orders("PO-C")), 1)
        (duplicate,) = self._children(again).filtered(
            lambda r: r.edi_exchange_state == "input_processed_error"
        )
        self.assertIn("PO PO-A already exists", duplicate.exchange_error)

    def test_processing_the_file_again_does_not_split_it_again(self):
        record = self._receive(_order_text(po_number="PO-A"))
        count = len(self._children(record))
        record.edi_exchange_state = "input_received"
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            record.action_exchange_process()
        self.assertEqual(len(self._children(record)), count)
        self.assertEqual(len(self._orders("PO-A")), 1)
