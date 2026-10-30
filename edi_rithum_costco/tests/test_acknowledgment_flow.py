"""Every 850 we receive gets a 997, whether it was processed or refused."""

import base64
from unittest import mock

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from .test_flow_850 import SENDER, _order_text

OUR_ID = "OURID"


class TestAcknowledgmentFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def _receive(self, text: str):
        """An inbound record holding ``text``, as the receive step leaves it."""
        record = self.backend.create_record(
            "rithum_in",
            {"exchange_file": base64.b64encode(text.encode("cp1252"))},
        )
        record.edi_exchange_state = "input_received"
        return record

    def _process(self, record):
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            record.action_exchange_process()
        return send

    def _ack_text(self, record) -> str:
        return base64.b64decode(record.ack_exchange_id.exchange_file).decode("cp1252")

    def test_a_processed_order_is_acknowledged_as_accepted(self):
        record = self._receive(_order_text(po_number="PO-ACK"))
        send = self._process(record)
        self.assertEqual(record.edi_exchange_state, "input_processed")
        ack = record.ack_exchange_id
        self.assertEqual(ack.type_id.code, "rithum_997_out")
        self.assertEqual(ack.parent_id, record)
        send.assert_called_once()
        text = self._ack_text(record)
        self.assertIn("AK5*A~", text)
        self.assertIn("AK9*A*1*1*1~", text)
        control = text.split("~")[0].split("*")[13]
        self.assertEqual(ack.x12_control_number, str(int(control)))
        # the file is named by that number, as Rithum recommends
        self.assertEqual(ack.exchange_filename, f"HUB{int(control):09d}.intchg")

    def test_the_answer_goes_back_to_the_sender_as_the_id_it_was_sent_to(self):
        record = self._receive(_order_text(po_number="PO-ROUTE"))
        self._process(record)
        isa = self._ack_text(record).split("~")[0].split("*")
        self.assertEqual(isa[6].strip(), OUR_ID)
        self.assertEqual(isa[8].strip(), SENDER)
        self.assertEqual(isa[7], "ZZ")  # the qualifier the sender used

    def test_a_refused_file_gets_a_rejecting_997(self):
        text = _order_text(po_number="PO-BAD").replace(
            "BEG*00*SA*PO-BAD**20200310~", ""
        )
        record = self._receive(text)
        self._process(record)
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        text = self._ack_text(record)
        self.assertIn("AK3*BEG*2**3~", text)  # mandatory segment missing
        self.assertIn("AK5*R*4~", text)  # and the segment count is off
        self.assertIn("AK9*R*1*1*0~", text)

    def test_a_business_error_is_still_acknowledged_as_accepted(self):
        # The 997 only says the file was well formed; the unknown item is ours to fix.
        record = self._receive(_order_text(po_number="PO-SKU", vendor_sku="000000"))
        self._process(record)
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("AK5*A~", self._ack_text(record))

    def test_a_record_is_acknowledged_only_once(self):
        record = self._receive(_order_text(po_number="PO-ONCE"))
        self._process(record)
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            self.assertFalse(record.x12_acknowledge())
        self.assertEqual(len(record.related_exchange_ids), 1)

    def test_a_failing_acknowledgment_does_not_undo_the_processing(self):
        record = self._receive(_order_text(po_number="PO-FAIL"))
        with (
            mock.patch(
                "odoo.addons.edi_x12.x12.tset_997.acknowledge",
                side_effect=ValueError("the 997 could not be built"),
            ),
            mute_logger("odoo.addons.edi_x12.models.edi_exchange_record"),
        ):
            self._process(record)
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertTrue(record.related_record_ids)
        self.assertIn("could not be built", record.related_exchange_ids.exchange_error)

    def test_a_backend_without_an_id_still_answers_as_the_id_the_file_names(self):
        self.backend.x12_sender_id = False
        record = self._receive(_order_text(po_number="PO-NOID"))
        self._process(record)
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertFalse(record.ack_exchange_id.exchange_error)
        isa = self._ack_text(record).split("~")[0].split("*")
        self.assertEqual(isa[6].strip(), OUR_ID)

    def test_a_record_without_a_file_is_not_acknowledged(self):
        record = self.backend.create_record("rithum_in", {})
        self.assertFalse(record.x12_acknowledge())
        self.assertFalse(record.related_exchange_ids)
