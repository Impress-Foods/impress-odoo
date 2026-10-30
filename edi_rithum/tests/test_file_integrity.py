"""Rithum puts the MD5 of each file in its name: a damaged download is refused."""

import base64
import hashlib
from unittest import mock

from odoo.tests.common import TransactionCase

from odoo.addons.edi_core_oca.exceptions import EDIValidationError

CONTENT = b"ISA*00*          *00*          *12*HUBTESTID00001 *ZZ*SENDER0001     ~"
MD5 = hashlib.md5(CONTENT).hexdigest()


class TestFileIntegrity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env.ref("edi_rithum.rithum_backend")
        cls.handler = cls.env["edi.rithum.handler.input.validate"]

    def _record(self, name, content=CONTENT, state="input_received"):
        return self.backend.create_record(
            "rithum_in",
            {
                "exchange_filename": name,
                "exchange_file": base64.b64encode(content),
                "edi_exchange_state": state,
            },
        )

    def test_a_file_that_matches_its_hash_passes(self):
        record = self._record(f"1000000001.md5{MD5}.intchg")
        self.assertIsNone(self.handler.input_validate(record))

    def test_the_hash_in_the_name_may_be_upper_case(self):
        record = self._record(f"1000000001.md5{MD5.upper()}.intchg")
        self.assertIsNone(self.handler.input_validate(record))

    def test_a_file_that_differs_from_its_hash_is_refused(self):
        record = self._record(f"1000000001.md5{MD5}.intchg", content=CONTENT + b"x")
        with self.assertRaisesRegex(EDIValidationError, "damaged in transfer"):
            self.handler.input_validate(record)

    def test_a_truncated_file_is_refused(self):
        record = self._record(f"1000000001.md5{MD5}.intchg", content=CONTENT[:-5])
        with self.assertRaises(EDIValidationError):
            self.handler.input_validate(record)

    def test_a_name_without_a_hash_is_not_checked(self):
        for name in ("HUB000000016.intchg", "orders.1234.intchg", ""):
            with self.subTest(name=name):
                record = self._record(name)
                self.assertIsNone(self.handler.input_validate(record))

    def test_a_damaged_download_stops_at_validation_and_is_never_processed(self):
        record = self._record(
            f"1000000001.md5{MD5}.intchg", content=b"", state="input_pending"
        )
        storage_handler = self.env.registry["edi.oca.storage.handler"]
        with mock.patch.object(
            storage_handler, "receive", return_value=CONTENT + b"damaged"
        ):
            record.action_exchange_receive()
        self.assertEqual(record.edi_exchange_state, "validate_error")
        self.assertIn("MD5", record.exchange_error)

    def test_an_intact_download_goes_on_to_be_processed(self):
        record = self._record(
            f"1000000001.md5{MD5}.intchg", content=b"", state="input_pending"
        )
        storage_handler = self.env.registry["edi.oca.storage.handler"]
        with mock.patch.object(storage_handler, "receive", return_value=CONTENT):
            record.action_exchange_receive()
        self.assertEqual(record.edi_exchange_state, "input_received")
