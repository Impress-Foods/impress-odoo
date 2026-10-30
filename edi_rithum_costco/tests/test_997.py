"""997s: our acknowledgments render and read back."""

from __future__ import annotations

import re
import unittest
from datetime import datetime

from odoo.addons.edi_x12.x12 import outbound, simple_xml, tset_997
from odoo.addons.edi_x12.x12.engine import validate_document

from .maps import MAP_PATH
from .test_flow_850 import _order_text

try:
    from odoo.tests.common import BaseCase as TestCaseBase
except ImportError:  # pragma: no cover - standalone run
    TestCaseBase = unittest.TestCase

if "test_tags" not in vars(TestCaseBase):
    TestCaseBase.test_tags = {"standard", "at_install"}


def _envelope() -> outbound.Envelope:
    return outbound.Envelope(
        sender_id="DSCO",
        receiver_id="ABCDEF",
        control_number=1,
        production=False,
        sent_at=datetime(2026, 10, 27, 16, 11),
        interchange_version="00401",
        functional_version="004010",
        functional_id="FA",
    )


def _accepted() -> tset_997.Acknowledgment:
    return tset_997.Acknowledgment(
        functional_id="IB",
        group_control="1",
        status=tset_997.ACCEPTED,
        transactions=(
            tset_997.AcknowledgedTransaction("846", "0001", tset_997.ACCEPTED),
        ),
    )


def _rejected() -> tset_997.Acknowledgment:
    return tset_997.Acknowledgment(
        functional_id="IB",
        group_control="1",
        status=tset_997.REJECTED,
        transactions=(
            tset_997.AcknowledgedTransaction(
                "846",
                "0001",
                tset_997.REJECTED,
                errors=(tset_997.SegmentError("BIA", 3, "3"),),
            ),
        ),
    )


def _render(ack: tset_997.Acknowledgment) -> str:
    tree = outbound.interchange(_envelope(), tset_997.build_body(ack), "997", "0001")
    return outbound.render(tree, MAP_PATH)


class TestOutbound997(TestCaseBase):
    def test_accepted_acknowledgment_validates(self):
        outcome = validate_document(_render(_accepted()), MAP_PATH)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.issues, ())

    def test_accepted_round_trip(self):
        ack = _accepted()
        outcome = validate_document(_render(ack), MAP_PATH)
        (read_back,) = tset_997.read_functional_acknowledgments(
            simple_xml.parse(outcome.xml)
        )
        self.assertEqual(read_back, ack)

    def test_rejected_round_trip_keeps_the_segment_error(self):
        ack = _rejected()
        outcome = validate_document(_render(ack), MAP_PATH)
        (read_back,) = tset_997.read_functional_acknowledgments(
            simple_xml.parse(outcome.xml)
        )
        self.assertEqual(read_back, ack)
        self.assertEqual(read_back.transactions[0].errors[0].segment_id, "BIA")

    def test_a_status_outside_the_codes_is_refused(self):
        bad = tset_997.Acknowledgment(
            functional_id="IB",
            group_control="1",
            status="Z",
            transactions=(),
        )
        with self.assertRaises(ValueError):
            tset_997.build_body(bad)


ENVELOPE_OUT = outbound.Envelope(
    sender_id="ABCDEF",
    receiver_id="COSTCO",
    control_number=77,
    production=False,
    sent_at=datetime(2026, 10, 27, 16, 11),
    interchange_version="00401",
    functional_version="004010",
    functional_id="FA",
)


class TestAcknowledgeInbound(TestCaseBase):
    """Our 997 for a document we received, built from its validation outcome."""

    def _acknowledge(self, text: str) -> tset_997.Acknowledgment:
        outcome = validate_document(text, MAP_PATH)
        ack_text = tset_997.acknowledge(text, outcome, ENVELOPE_OUT, MAP_PATH)
        root = simple_xml.parse(validate_document(ack_text, MAP_PATH).xml)
        (ack,) = tset_997.read_functional_acknowledgments(root)
        return ack

    def test_accepted_document_gets_an_accepting_997(self):
        ack = self._acknowledge(_order_text())
        self.assertEqual(ack.functional_id, "PO")
        self.assertEqual(ack.status, tset_997.ACCEPTED)
        self.assertEqual(ack.transactions[0].tset, "850")
        self.assertEqual(ack.transactions[0].control_number, "0001")
        self.assertEqual(ack.transactions[0].errors, ())

    def test_rejected_document_gets_a_rejecting_997_naming_the_segment(self):
        text = _order_text().replace("BEG*00*SA*PO-7741**20200310~", "")
        ack = self._acknowledge(text)
        self.assertEqual(ack.status, tset_997.REJECTED)
        self.assertEqual(ack.transactions[0].status, tset_997.REJECTED)
        self.assertEqual(ack.transactions[0].errors[0].segment_id, "BEG")
        self.assertEqual(ack.transactions[0].errors[0].position, 2)


def _interchange_of(*po_numbers: str) -> str:
    """One group holding one 850 per PO number, each with its own ST02."""
    texts = [_order_text(po_number=number) for number in po_numbers]
    first = texts[0]
    extra = ""
    for control, text in enumerate(texts[1:], start=2):
        block = re.search(r"ST\*850\*0001~.*?SE\*\d+\*0001~", text, re.DOTALL).group(0)
        block = block.replace("ST*850*0001~", f"ST*850*{control:04d}~")
        extra += re.sub(r"SE\*(\d+)\*0001~", rf"SE*\1*{control:04d}~", block)
    end = first.index("GE*")
    return first[:end] + extra + first[end:].replace("GE*1*", f"GE*{len(texts)}*", 1)


class TestAcknowledgeGroups(TestCaseBase):
    """A group with several purchase orders gets one 997 with a status for each."""

    def _acknowledge(self, text: str) -> tset_997.Acknowledgment:
        outcome = validate_document(text, MAP_PATH)
        ack_text = tset_997.acknowledge(text, outcome, ENVELOPE_OUT, MAP_PATH)
        root = simple_xml.parse(validate_document(ack_text, MAP_PATH).xml)
        (ack,) = tset_997.read_functional_acknowledgments(root)
        return ack

    def test_every_transaction_in_the_group_is_acknowledged(self):
        ack = self._acknowledge(_interchange_of("PO-A", "PO-B", "PO-C"))
        self.assertEqual(ack.status, tset_997.ACCEPTED)
        self.assertEqual(
            [(t.control_number, t.status) for t in ack.transactions],
            [("0001", "A"), ("0002", "A"), ("0003", "A")],
        )

    def test_a_bad_transaction_rejects_only_itself(self):
        text = _interchange_of("PO-A", "PO-B").replace("BEG*00*SA*PO-B**20200310~", "")
        ack = self._acknowledge(text)
        self.assertEqual(ack.status, tset_997.PARTIALLY_ACCEPTED)
        first, second = ack.transactions
        self.assertEqual((first.status, first.errors), (tset_997.ACCEPTED, ()))
        self.assertEqual(second.status, tset_997.REJECTED)
        self.assertEqual(second.errors[0].segment_id, "BEG")
        self.assertEqual(second.errors[0].position, 2)
        self.assertEqual(second.errors[0].syntax_code, "3")

    def test_an_error_outside_the_transactions_rejects_the_group(self):
        text = _interchange_of("PO-A", "PO-B").replace("GE*2*", "GE*3*", 1)
        ack = self._acknowledge(text)
        self.assertEqual(ack.status, tset_997.REJECTED)
        self.assertEqual({t.status for t in ack.transactions}, {tset_997.REJECTED})

    def test_an_interchange_with_two_groups_is_refused(self):
        text = _order_text()
        group = re.search(r"GS\*.*?GE\*\d+\*\d+~", text, re.DOTALL).group(0)
        doubled = text.replace(group, group + group)
        outcome = validate_document(doubled, MAP_PATH)
        with self.assertRaisesRegex(ValueError, "one functional group"):
            tset_997.acknowledge(doubled, outcome, ENVELOPE_OUT, MAP_PATH)

    def test_input_that_is_not_an_interchange_is_refused(self):
        outcome = validate_document("garbage", MAP_PATH)
        with self.assertRaises(ValueError):
            tset_997.acknowledge("garbage", outcome, ENVELOPE_OUT, MAP_PATH)

    def test_the_application_codes_are_exchanged_from_the_group_acknowledged(self):
        text = re.sub(
            r"GS\*PO\*[^*]*\*[^*]*\*", "GS*PO*THEIRAPP*OURAPP*", _order_text()
        )
        outcome = validate_document(text, MAP_PATH)
        ack_text = tset_997.acknowledge(text, outcome, ENVELOPE_OUT, MAP_PATH)
        isa, gs = ack_text.split("~")[:2]
        self.assertEqual(gs.split("*")[2:4], ["OURAPP", "THEIRAPP"])
        self.assertEqual(isa.split("*")[6].strip(), "ABCDEF")  # the ISA IDs stay ours


class TestRejectionCodes(TestCaseBase):
    """A rejecting 997 says why, with the X12 codes pyx12 reports."""

    def _acknowledge(self, text: str) -> tset_997.Acknowledgment:
        outcome = validate_document(text, MAP_PATH)
        ack_text = tset_997.acknowledge(text, outcome, ENVELOPE_OUT, MAP_PATH)
        root = simple_xml.parse(validate_document(ack_text, MAP_PATH).xml)
        (ack,) = tset_997.read_functional_acknowledgments(root)
        return ack

    def _transaction(self, text: str) -> tset_997.AcknowledgedTransaction:
        (transaction,) = self._acknowledge(text).transactions
        return transaction

    def test_a_missing_mandatory_segment_is_code_3(self):
        text = _order_text().replace("BEG*00*SA*PO-7741**20200310~", "")
        (error,) = self._transaction(text).errors
        self.assertEqual((error.segment_id, error.syntax_code), ("BEG", "3"))

    def test_a_segment_the_map_does_not_have_is_code_1(self):
        text = _order_text().replace("TD5*", "ZZZ*", 1)
        errors = self._transaction(text).errors
        self.assertEqual((errors[0].segment_id, errors[0].syntax_code), ("ZZZ", "1"))

    def test_a_segment_over_its_maximum_use_is_code_5(self):
        text = _order_text().replace("CTT*1~", "CTT*1~CTT*1~")
        transaction = self._transaction(text)
        self.assertEqual(
            [(e.segment_id, e.syntax_code) for e in transaction.errors], [("CTT", "5")]
        )
        # The extra segment also throws the SE count off: a transaction-level reason.
        self.assertEqual(transaction.reason_codes, ("4",))

    def test_a_wrong_segment_count_is_a_transaction_reason_not_a_segment_error(self):
        text = re.sub(r"SE\*\d+", "SE*99", _order_text())
        transaction = self._transaction(text)
        self.assertEqual(transaction.status, tset_997.REJECTED)
        self.assertEqual(transaction.errors, ())
        self.assertEqual(transaction.reason_codes, ("4",))

    def test_reason_codes_survive_a_round_trip_and_stop_at_five(self):
        ack = tset_997.Acknowledgment(
            functional_id="PO",
            group_control="1",
            status=tset_997.REJECTED,
            transactions=(
                tset_997.AcknowledgedTransaction(
                    "850",
                    "0001",
                    tset_997.REJECTED,
                    reason_codes=("1", "2", "3", "4", "5", "6"),
                ),
            ),
            reason_codes=("5", "6"),
        )
        envelope = ENVELOPE_OUT
        tree = outbound.interchange(envelope, tset_997.build_body(ack), "997", "0001")
        text = outbound.render(tree, MAP_PATH)
        (read_back,) = tset_997.read_functional_acknowledgments(
            simple_xml.parse(validate_document(text, MAP_PATH).xml)
        )
        self.assertEqual(read_back.reason_codes, ("5", "6"))
        self.assertEqual(
            read_back.transactions[0].reason_codes, ("1", "2", "3", "4", "5")
        )
