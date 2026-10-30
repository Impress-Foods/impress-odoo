"""Files from Costco are sorted by their sender and content, and its 997s read."""

import base64
from datetime import datetime
from unittest import mock

from odoo.tests.common import TransactionCase

from odoo.addons.edi_x12.x12 import outbound, tset_997

from ..documents import tset_856
from .maps import MAP_PATH
from .test_856 import _confirmation
from .test_flow_850 import SENDER, _order_text

OUR_ID = "OURID"


def _costco_envelope(functional_id: str) -> outbound.Envelope:
    """An interchange as Costco sends it: their qualifier 12, our ID as receiver."""
    return outbound.Envelope(
        sender_id=SENDER,
        receiver_id=OUR_ID,
        control_number=131653,
        production=False,
        sent_at=datetime(2026, 10, 29, 15, 11),
        interchange_version="00401",
        functional_version="004010",
        functional_id=functional_id,
        sender_qualifier="12",
    )


def _acknowledgment(group_control, status, transaction_status=None, **transaction):
    return tset_997.Acknowledgment(
        functional_id="SH",
        group_control=group_control,
        status=status,
        transactions=(
            tset_997.AcknowledgedTransaction(
                "856", "0001", transaction_status or status, **transaction
            ),
        ),
    )


def _file_997(*acknowledgments) -> str:
    """Costco's 997 file holding one acknowledgment per group."""
    # One group per interchange is all pyx12 reads, so a file holds one.
    (ack,) = acknowledgments
    body = tset_997.build_body(ack)
    tree = outbound.interchange(_costco_envelope("FA"), body, "997", "0001")
    return outbound.render(tree, MAP_PATH)


class TestInboundRouting(TransactionCase):
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
        cls.partner = partner

    def _receive(self, text: str):
        return self.backend.create_record(
            "rithum_in",
            {
                "exchange_file": base64.b64encode(text.encode("cp1252")),
                "edi_exchange_state": "input_received",
            },
        )

    def _process(self, record):
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            record.action_exchange_process()
        return record

    def _sent_file(self, control="16", state="output_sent"):
        """A confirmation we sent, as the record the 997 will refer to."""
        return self.backend.create_record(
            "costco_856_out",
            {
                "x12_control_number": control,
                "edi_exchange_state": state,
                "model": "res.partner",
                "res_id": self.partner.id,
            },
        )

    def _chatter(self) -> str:
        return " ".join(self.partner.message_ids.mapped("body"))

    def test_a_purchase_order_file_makes_orders(self):
        record = self._process(self._receive(_order_text(po_number="PO-ROUTED")))
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertEqual(record.x12_document, "850")
        order = self.env["sale.order"].search([("client_order_ref", "=", "PO-ROUTED")])
        self.assertEqual(order.origin_exchange_record_id, record)

    def test_a_997_is_not_treated_as_a_purchase_order(self):
        sent = self._sent_file()
        record = self._process(self._receive(_file_997(_acknowledgment("16", "A"))))
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertEqual(record.x12_document, "997")
        self.assertFalse(
            self.env["sale.order"].search(
                [("origin_exchange_record_id", "=", record.id)]
            )
        )
        self.assertEqual(record.parent_id, sent)

    def test_a_997_is_never_acknowledged(self):
        self._sent_file()
        record = self._process(self._receive(_file_997(_acknowledgment("16", "A"))))
        children = self.env["edi.exchange.record"].search(
            [("parent_id", "=", record.id)]
        )
        self.assertFalse(children)
        self.assertFalse(record.ack_exchange_id)

    def test_an_accepting_997_marks_the_file_we_sent_as_processed(self):
        sent = self._sent_file()
        record = self._process(self._receive(_file_997(_acknowledgment("16", "A"))))
        self.assertEqual(sent.edi_exchange_state, "output_sent_and_processed")
        self.assertEqual(sent.ack_exchange_id, record)
        self.assertIn("ACK file received", self._chatter())

    def test_a_rejecting_997_marks_it_and_says_why(self):
        sent = self._sent_file()
        rejection = _acknowledgment(
            "16",
            tset_997.REJECTED,
            errors=(tset_997.SegmentError("BSN", 2, "2"),),
            reason_codes=("4",),
        )
        record = self._process(self._receive(_file_997(rejection)))
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertEqual(sent.edi_exchange_state, "output_sent_and_error")
        chatter = self._chatter()
        self.assertIn("ACK file received but contains errors", chatter)
        self.assertIn("Segment BSN, position 2, error code 2", chatter)
        self.assertIn("Reason code 4", chatter)

    def test_a_997_for_a_file_we_did_not_send_is_an_error(self):
        record = self._process(self._receive(_file_997(_acknowledgment("99", "A"))))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("control number 99", record.exchange_error)

    def test_leading_zeros_in_the_control_number_do_not_matter(self):
        sent = self._sent_file(control="16")
        self._process(self._receive(_file_997(_acknowledgment("000016", "A"))))
        self.assertEqual(sent.edi_exchange_state, "output_sent_and_processed")

    def test_a_document_we_do_not_handle_is_an_error_not_a_success(self):
        tree = outbound.interchange(
            _costco_envelope("SH"),
            tset_856.build_body(_confirmation()),
            "856",
            "0001",
        )
        record = self._process(self._receive(outbound.render(tree, MAP_PATH)))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("not supported", record.exchange_error)
        self.assertFalse(record.x12_document)

    def test_a_file_that_is_not_x12_is_an_error(self):
        record = self._process(self._receive("this is not an interchange"))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")

    def test_another_partners_file_is_not_read_by_costcos_mapping(self):
        other = self.env["edi.rithum.partner"].create(
            {
                "name": "Another retailer",
                "x12_id": "OTHERRETAILER01",
                "map_set": "edi_rithum_costco/x12_maps",
                "intake_model": "edi.rithum.intake",
            }
        )
        text = _order_text(po_number="PO-ELSEWHERE").replace(SENDER, "OTHERRETAILER01")
        record = self._process(self._receive(text))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("not supported", record.exchange_error)
        self.assertIn(other.name, record.exchange_error)
        self.assertFalse(
            self.env["sale.order"].search([("client_order_ref", "=", "PO-ELSEWHERE")])
        )

    def test_a_file_from_nobody_we_know_is_refused_and_answered(self):
        text = _order_text(po_number="PO-STRANGER").replace(SENDER, "STRANGERSENDER1")
        record = self._process(self._receive(text))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("No Rithum partner", record.exchange_error)
        self.assertTrue(record.ack_exchange_id)
        self.assertFalse(
            self.env["sale.order"].search([("client_order_ref", "=", "PO-STRANGER")])
        )

    def test_the_order_remembers_the_partner_its_file_came_from(self):
        record = self._process(self._receive(_order_text(po_number="PO-WHO")))
        self.assertEqual(
            record.rithum_partner_id,
            self.env.ref("edi_rithum_costco.rithum_partner_costco"),
        )
