"""Rithum partners are told apart by interchange ID, and their files are routed."""

import base64
from datetime import datetime
from unittest import mock

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.edi_x12.x12 import outbound, tset_997

MAPS = "edi_rithum/x12_maps"
THEIRS, OURS = "PARTNERID", "OURID"


def _isa(sender: str, receiver: str, group: str, transaction_set: str) -> str:
    """A bare interchange: enough for the router, which only reads who and what."""
    return (
        f"ISA*00*          *00*          *ZZ*{sender:<15}*ZZ*{receiver:<15}"
        f"*261030*1508*U*00401*000000001*0*T*:~"
        f"GS*{group}*{sender}*{receiver}*20261030*1508*1*X*004010~"
        f"ST*{transaction_set}*0001~SE*2*0001~GE*1*1~IEA*1*000000001~"
    )


def _file_997(sender: str, group_control: str, status: str) -> str:
    ack = tset_997.Acknowledgment(
        functional_id="SH",
        group_control=group_control,
        status=status,
        transactions=(tset_997.AcknowledgedTransaction("856", "0001", status),),
    )
    envelope = outbound.Envelope(
        sender_id=sender,
        receiver_id=OURS,
        control_number=7,
        production=False,
        sent_at=datetime(2026, 10, 30, 15, 8),
        interchange_version="00401",
        functional_version="004010",
        functional_id="FA",
    )
    tree = outbound.interchange(envelope, tset_997.build_body(ack), "997", "0001")
    from odoo.tools import file_path

    return outbound.render(tree, file_path(MAPS))


class TestRithumPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env.ref("edi_rithum.rithum_backend")
        cls.backend.x12_sender_id = OURS
        cls.partner = cls.env["edi.rithum.partner"].create(
            {
                "name": "A retailer",
                "x12_id": THEIRS,
                "map_set": MAPS,
                "intake_model": "edi.rithum.intake",
            }
        )

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

    def test_a_partner_is_found_from_the_interchange_id(self):
        found = self.env["edi.rithum.partner"].from_sender(self.backend, THEIRS)
        self.assertEqual(found, self.partner)
        self.assertFalse(self.env["edi.rithum.partner"].from_sender(self.backend, "X"))

    def test_two_partners_cannot_share_an_interchange_id(self):
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            self.partner.copy({"name": "Same ID", "x12_id": THEIRS})

    def test_the_partner_gives_its_maps_and_its_intake(self):
        self.assertTrue(self.partner.map_path().endswith("edi_rithum/x12_maps"))
        self.assertEqual(self.partner.intake()._name, "edi.rithum.intake")

    def test_a_file_that_answers_nothing_is_addressed_to_the_partner(self):
        envelope = self.partner.x12_envelope("IB")
        self.assertEqual(
            (envelope.receiver_qualifier, envelope.receiver_id), ("ZZ", THEIRS)
        )
        self.assertEqual((envelope.sender_qualifier, envelope.sender_id), ("ZZ", OURS))

    def test_our_identity_with_a_partner_can_differ_from_the_backends(self):
        self.partner.write({"own_qualifier": "01", "own_id": "OURS-WITH-THEM"})
        envelope = self.partner.x12_envelope("IB")
        self.assertEqual(
            (envelope.sender_qualifier, envelope.sender_id), ("01", "OURS-WITH-THEM")
        )

    def test_a_partner_without_an_interchange_id_cannot_be_written_to(self):
        self.partner.x12_id = False
        with self.assertRaisesRegex(UserError, "interchange ID"):
            self.partner.x12_envelope("IB")

    def test_a_file_from_an_unknown_sender_is_refused(self):
        record = self._process(self._receive(_isa("STRANGER", OURS, "PO", "850")))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        self.assertIn("No Rithum partner", record.exchange_error)
        self.assertFalse(record.rithum_partner_id)

    def test_a_document_the_partner_does_not_read_is_an_error(self):
        record = self._process(self._receive(_isa(THEIRS, OURS, "PO", "850")))
        self.assertEqual(record.edi_exchange_state, "input_processed_error")
        # the error names the partner whose module does not read the document
        self.assertIn("not supported", record.exchange_error)
        self.assertIn("A retailer", record.exchange_error)

    def test_a_997_updates_the_file_it_answers(self):
        sent = self.backend.create_record(
            "rithum_997_out",
            {"x12_control_number": "16", "edi_exchange_state": "output_sent"},
        )
        record = self._process(self._receive(_file_997(THEIRS, "16", "A")))
        self.assertEqual(record.edi_exchange_state, "input_processed")
        self.assertEqual(record.rithum_partner_id, self.partner)
        self.assertEqual(record.x12_document, "997")
        self.assertEqual(sent.edi_exchange_state, "output_sent_and_processed")
        self.assertEqual(record.parent_id, sent)

    def test_a_997_is_never_answered(self):
        self.backend.create_record(
            "rithum_997_out",
            {"x12_control_number": "16", "edi_exchange_state": "output_sent"},
        )
        record = self._process(self._receive(_file_997(THEIRS, "16", "A")))
        self.assertFalse(record.ack_exchange_id)
