"""The generic X12 library: nothing here needs a partner's maps."""

import logging
import threading
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

from defusedxml import EntitiesForbidden

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..x12 import engine, outbound
from ..x12.fields import parse_date, parse_decimal, time_code
from ..x12.reading import (
    isa_control_number,
    isa_receiver,
    isa_sender,
    isa_usage_indicator,
    qualifier_pairs,
    transactions,
)
from ..x12.simple_xml import Loop, Segment, parse, walk_loops

NO_MAPS = "/nonexistent/x12_maps"


def _interchange(*segments: Segment) -> str:
    envelope = outbound.Envelope(
        sender_id="SENDER",
        receiver_id="RECEIVER",
        control_number=1,
        production=False,
        sent_at=datetime(2026, 10, 27, 16, 11),
        interchange_version="00401",
        functional_version="004010",
        functional_id="PO",
    )
    tree = outbound.interchange(envelope, Loop("BODY", list(segments)), "850", "0001")
    return outbound.to_x12(outbound.to_simple_xml(tree))


def _beg(po_number: str) -> Segment:
    return Segment("BEG", {"BEG01": "00", "BEG02": "SA", "BEG03": po_number})


class TestNormalize(TransactionCase):
    def test_trailing_spaces_are_dropped_but_isa_is_left_alone(self):
        text = _interchange(_beg("PO-1"))
        padded = text.replace("PO-1", "PO-1   ")
        normalized = engine._normalize(padded)
        self.assertIn("BEG*00*SA*PO-1~", normalized)
        isa_end = text.index("~")
        self.assertEqual(normalized[: isa_end + 1], text[: isa_end + 1])

    def test_accents_become_their_base_letters(self):
        text = _interchange(_beg("Été-çà"))
        self.assertIn("BEG*00*SA*Ete-ca~", engine._normalize(text))

    def test_replacement_characters_become_a_question_mark(self):
        for broken in ("�", "ï¿½"):
            with self.subTest(broken=broken):
                text = _interchange(_beg(f"A{broken}B"))
                self.assertIn("BEG*00*SA*A?B~", engine._normalize(text))

    def test_letters_without_an_ascii_form_become_a_question_mark(self):
        self.assertEqual(engine._fold("straße"), "stra?e")

    def test_text_that_is_not_an_interchange_is_only_folded(self):
        self.assertEqual(engine._normalize("héllo  "), "hello  ")


class TestRestoreText(TransactionCase):
    def _pid(self, description: str) -> Segment:
        return Segment("PID", {"PID01": "F", "PID02": "08", "PID05": description})

    def test_pid05_values_skip_segments_without_a_description(self):
        text = _interchange(
            self._pid("Café  "), Segment("PID", {"PID01": "F"}), self._pid("Thé")
        )
        self.assertEqual(engine._pid05_values(text), ["Café", "Thé"])

    def test_original_text_replaces_the_checked_text(self):
        text = _interchange(self._pid("Café  "))
        xml = "<seg id='PID'><ele id='PID05'>Cafe</ele></seg>"
        self.assertIn("<ele id='PID05'>Café</ele>", engine._restore_text(xml, text))

    def test_xml_special_characters_stay_escaped(self):
        text = _interchange(self._pid("Thé & <Café>"))
        xml = "<ele id='PID05'>The &amp; &lt;Cafe&gt;</ele>"
        self.assertEqual(
            engine._restore_text(xml, text),
            "<ele id='PID05'>Thé &amp; &lt;Café&gt;</ele>",
        )

    def test_a_different_number_of_descriptions_leaves_the_xml_alone(self):
        text = _interchange(self._pid("Café"), self._pid("Thé"))
        xml = "<ele id='PID05'>Cafe</ele>"
        self.assertEqual(engine._restore_text(xml, text), xml)

    def test_a_value_that_does_not_fold_to_the_checked_one_is_not_restored(self):
        text = _interchange(self._pid("Café"))
        xml = "<ele id='PID05'>Other</ele>"
        self.assertEqual(engine._restore_text(xml, text), xml)


class TestValidateDocument(TransactionCase):
    @mute_logger("odoo.addons.edi_x12.x12.engine")
    def test_missing_maps_reject_the_document_with_a_reason(self):
        outcome = engine.validate_document(_interchange(_beg("PO-1")), NO_MAPS)
        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.issues)
        self.assertIsNone(outcome.xml)

    @mute_logger("odoo.addons.edi_x12.x12.engine")
    def test_unreadable_input_is_rejected_not_raised(self):
        outcome = engine.validate_document("ISA*garbage~", NO_MAPS)
        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.issues)


class TestValidationRun(TransactionCase):
    def test_a_document_is_validated_once_and_keeps_its_xml(self):
        with mock.patch.object(
            engine, "_run", return_value=engine._Run(True, (), "<x12simple/>")
        ) as run:
            outcome = engine.validate_document(_interchange(_beg("PO-1")), NO_MAPS)
        run.assert_called_once()
        self.assertTrue(run.call_args.kwargs["want_xml"])
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.xml, "<x12simple/>")

    def test_when_the_xml_writer_fails_the_document_is_validated_without_it(self):
        issues = (engine.Issue(engine.SEVERITY_ERROR, 2, "segment not in the map"),)
        with mock.patch.object(
            engine,
            "_run",
            side_effect=[engine._XmlWriterFailure(), engine._Run(False, issues, None)],
        ) as run:
            outcome = engine.validate_document(_interchange(_beg("PO-1")), NO_MAPS)
        self.assertEqual(
            [call.kwargs["want_xml"] for call in run.call_args_list], [True, False]
        )
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.issues, issues)

    def test_a_rejected_document_carries_no_xml(self):
        issues = (engine.Issue(engine.SEVERITY_ERROR, 2, "bad"),)
        with mock.patch.object(
            engine, "_run", return_value=engine._Run(False, issues, "<partial/>")
        ):
            outcome = engine.validate_document(_interchange(_beg("PO-1")), NO_MAPS)
        self.assertFalse(outcome.ok)
        self.assertIsNone(outcome.xml)
        self.assertEqual(outcome.issues, issues)

    @mute_logger("odoo.addons.edi_x12.x12.engine")
    def test_the_reason_pyx12_could_not_read_a_document_is_kept(self):
        with mock.patch(
            "pyx12.x12n_document.x12n_document", side_effect=ValueError("boom")
        ):
            outcome = engine.validate_document(_interchange(_beg("PO-1")), NO_MAPS)
        self.assertFalse(outcome.ok)
        self.assertIn("ValueError: boom", outcome.issues[0].message)

    def test_findings_of_another_thread_are_not_captured(self):
        def record(message: str) -> logging.LogRecord:
            return logging.LogRecord(
                "pyx12", logging.ERROR, __file__, 1, message, None, None
            )

        records: list[logging.LogRecord] = []
        handler = engine._CaptureHandler(records)
        mine = record("Line:1 SEG:3 - mine")
        other: list[logging.LogRecord] = []
        thread = threading.Thread(target=lambda: other.append(record("theirs")))
        thread.start()
        thread.join()
        handler.emit(mine)
        handler.emit(other[0])
        self.assertEqual(records, [mine])

    def test_the_handler_is_removed_even_when_validation_fails(self):
        before = list(logging.getLogger("pyx12").handlers)
        engine.validate_document("ISA*garbage~", NO_MAPS)
        self.assertEqual(logging.getLogger("pyx12").handlers, before)


class TestIsaReaders(TransactionCase):
    ISA = (
        "ISA*00*          *00*          *12*SENDERQUAL     *ZZ*RECEIVER       "
        "*261030*1508*U*00401*000000046*0*T*:~GS*PO*A*B*20261030*1508*46*X*004010~"
    )

    def test_the_sender_is_the_qualifier_and_the_id_without_padding(self):
        self.assertEqual(isa_sender(self.ISA), ("12", "SENDERQUAL"))

    def test_the_receiver_is_the_qualifier_and_the_id_without_padding(self):
        self.assertEqual(isa_receiver(self.ISA), ("ZZ", "RECEIVER"))

    def test_the_control_number_is_read_as_a_number(self):
        self.assertEqual(isa_control_number(self.ISA), 46)

    def test_the_usage_indicator_is_test_or_production(self):
        self.assertEqual(isa_usage_indicator(self.ISA), "T")

    def test_text_that_is_not_an_interchange_is_refused(self):
        for reader in (
            isa_sender,
            isa_receiver,
            isa_control_number,
            isa_usage_indicator,
        ):
            with self.subTest(reader=reader.__name__), self.assertRaises(ValueError):
                reader("not an interchange")

    def test_leading_blanks_are_ignored(self):
        self.assertEqual(isa_sender("\n  " + self.ISA), ("12", "SENDERQUAL"))


class TestOutcome(TransactionCase):
    def test_the_summary_joins_the_findings(self):
        issues = (
            engine.Issue(engine.SEVERITY_ERROR, 2, "first"),
            engine.Issue(engine.SEVERITY_WARN, None, "second"),
        )
        summary = engine.Outcome(ok=False, issues=issues).summary
        self.assertEqual(summary, "[error] segment 2: first; [warn] second")


class TestSimpleXml(TransactionCase):
    XML = (
        "<x12simple><loop id='ST_LOOP'><seg id='ST'><ele id='ST01'>850</ele>"
        "<ele id='ST02'>  </ele></seg><loop id='N1_LOOP'><seg id='N1'>"
        "<ele id='N101'> ST </ele></seg></loop></loop></x12simple>"
    )

    def test_loops_segments_and_stripped_values(self):
        root = parse(self.XML)
        (st_loop,) = root.loops("ST_LOOP")
        self.assertEqual(st_loop.child_ids(), ["ST", "N1_LOOP"])
        self.assertEqual(st_loop.segment("ST").value("ST01"), "850")
        self.assertIsNone(st_loop.segment("ST").value("ST02"))
        (n1_loop,) = walk_loops(root, "N1_LOOP")
        self.assertEqual(n1_loop.segment("N1").required("N101"), "ST")

    def test_required_raises_for_an_absent_element(self):
        with self.assertRaises(KeyError):
            Segment("ST", {}).required("ST01")

    def test_wrong_root_and_unexpected_tags_are_refused(self):
        with self.assertRaises(ValueError):
            parse("<other/>")
        with self.assertRaises(ValueError):
            parse("<x12simple><junk/></x12simple>")
        with self.assertRaises(ValueError):
            parse("<x12simple><seg id='ST'><junk/></seg></x12simple>")

    def test_entity_declarations_are_refused(self):
        bomb = (
            '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "boom">]>'
            "<x12simple><seg id='ST'><ele id='ST01'>&a;</ele></seg></x12simple>"
        )
        with self.assertRaises(EntitiesForbidden):
            parse(bomb)


class TestReading(TransactionCase):
    def test_transactions_reads_only_the_requested_set(self):
        def st_loop(code: str) -> Loop:
            return Loop("ST_LOOP", [Segment("ST", {"ST01": code})])

        root = Loop("x12simple", [Loop("GS_LOOP", [st_loop("850"), st_loop("997")])])
        read = transactions(root, "850", lambda loop: loop.segment("ST").value("ST01"))
        self.assertEqual(read, ["850"])

    def test_qualifier_pairs(self):
        po1 = Segment(
            "PO1", {"PO108": "VN", "PO109": "A1", "PO110": "UP", "PO111": "B2"}
        )
        self.assertEqual(qualifier_pairs(po1, "PO1", 8, 12), {"VN": "A1", "UP": "B2"})
        self.assertEqual(qualifier_pairs(Segment("PO1", {}), "PO1", 8, 12), {})

    def test_a_qualifier_without_a_value_is_refused(self):
        with self.assertRaises(ValueError):
            qualifier_pairs(Segment("PO1", {"PO108": "VN"}), "PO1", 8, 10)


class TestFields(TransactionCase):
    def test_parse_decimal(self):
        self.assertEqual(parse_decimal("12.50", "PO104"), Decimal("12.50"))
        with self.assertRaisesRegex(ValueError, "PO104"):
            parse_decimal("abc", "PO104")

    def test_parse_date(self):
        self.assertEqual(parse_date("20261027", "BEG05"), date(2026, 10, 27))
        for bad in ("2026", "20261340", "abcdefgh"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "BEG05"):
                parse_date(bad, "BEG05")

    def test_time_codes_are_two_characters_like_the_buyers_samples(self):
        moment = datetime(2026, 10, 29, 12, 0)

        def code(hours: float) -> str:
            zone = timezone(timedelta(hours=hours))
            return time_code(moment.replace(tzinfo=zone))

        self.assertEqual(code(-5), "20")  # EST, in the samples
        self.assertEqual(code(-4), "21")  # EDT, in the samples
        self.assertEqual(code(-9), "16")  # the guide's Hawaii example
        self.assertEqual(code(-12), "13")
        self.assertEqual(code(-1), "24")
        self.assertEqual(code(1), "01")
        self.assertEqual(code(12), "12")
        self.assertEqual(code(0), "UT")
        for hours in range(-12, 13):
            self.assertEqual(len(code(hours)), 2)
        with self.assertRaises(ValueError):
            time_code(moment)
        with self.assertRaises(ValueError):
            code(5.5)


class TestReplyEnvelope(TransactionCase):
    def _backend(self):
        return self.env["edi.backend"].create(
            {
                "name": "X12 test",
                "backend_type_id": self.env.ref("edi_x12.edi_backend_x12").id,
                "x12_sender_id": "OURID",
            }
        )

    def test_a_reply_swaps_the_roles_of_the_file_it_answers(self):
        envelope = self._backend().x12_reply_envelope(TestIsaReaders.ISA, "FA")
        self.assertEqual(
            (envelope.receiver_qualifier, envelope.receiver_id),
            ("12", "SENDERQUAL"),
        )
        # we answer as the identity the file was addressed to, not the backend's
        self.assertEqual(
            (envelope.sender_qualifier, envelope.sender_id), ("ZZ", "RECEIVER")
        )
        self.assertEqual(envelope.functional_id, "FA")
        self.assertEqual(
            (envelope.interchange_version, envelope.functional_version),
            ("00401", "004010"),
        )

    def test_a_file_addressed_to_nobody_is_answered_as_the_backend(self):
        blank = TestIsaReaders.ISA.replace(
            "*ZZ*RECEIVER       *", "*ZZ*               *"
        )
        envelope = self._backend().x12_reply_envelope(blank, "FA")
        self.assertEqual(
            (envelope.sender_qualifier, envelope.sender_id), ("ZZ", "OURID")
        )

    def test_an_identity_can_be_given_for_a_file_with_nothing_to_answer(self):
        envelope = self._backend().x12_envelope(
            "12", "THEIRS", "IB", sender_qualifier="01", sender_id="OURS"
        )
        self.assertEqual(
            (envelope.sender_qualifier, envelope.sender_id), ("01", "OURS")
        )
        self.assertEqual(
            (envelope.receiver_qualifier, envelope.receiver_id), ("12", "THEIRS")
        )


class TestValidateOrRefuse(TransactionCase):
    def test_a_rejected_document_is_refused_with_the_findings(self):
        with (
            mute_logger("odoo.addons.edi_x12.x12.engine"),
            self.assertRaisesRegex(UserError, "Invalid X12 document"),
        ):
            self.env["edi.exchange.type"].x12_validate("ISA*garbage~", NO_MAPS)

    def test_an_accepted_document_returns_its_outcome(self):
        outcome = engine.Outcome(ok=True, issues=(), xml="<x12simple/>")
        with mock.patch(
            "odoo.addons.edi_x12.models.edi_exchange_type.validate_document",
            return_value=outcome,
        ):
            result = self.env["edi.exchange.type"].x12_validate("text", NO_MAPS)
        self.assertIs(result, outcome)


class TestBackendForm(TransactionCase):
    def test_the_x12_settings_are_on_the_backend_form(self):
        arch = self.env["edi.backend"].get_view(view_type="form")["arch"]
        for name in (
            "x12_sender_qualifier",
            "x12_sender_id",
            "x12_production",
            "x12_partner_scheme",
        ):
            with self.subTest(field=name):
                self.assertIn(f'name="{name}"', arch)
