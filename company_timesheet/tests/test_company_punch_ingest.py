from datetime import datetime

from odoo.tests.common import TransactionCase

from ..schema import PunchEvent


class TestCompanyPunchIngest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Punch = cls.env["company.punch"]
        cls.Timesheet = cls.env["company.timesheet"]
        cls.employee = cls.env["company.employee"].create({"name": "Punch Person"})
        cls.env["company.employee.source.ref"].create(
            {"employee_id": cls.employee.id, "source": "clock", "code": "E001"}
        )

    def _ingest(self, events, **kwargs):
        return self.Punch.ingest_punches(events, source="clock", **kwargs)

    def test_ingest_pairs_into_session(self):
        result = self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-05 08:00:00",
                    "direction": "in",
                },
                {
                    "external_id": "2",
                    "code": "E001",
                    "timestamp": "2026-01-05 12:00:00",
                    "direction": "out",
                },
            ],
            tz="UTC",
        )
        self.assertEqual(result.created, 2)
        self.assertEqual(result.sessions_rebuilt, 1)
        session = self.Timesheet.search([("employee_id", "=", self.employee.id)])
        self.assertEqual(len(session), 1)
        self.assertAlmostEqual(session.worked_hours, 4.0)

    def test_ingest_is_idempotent(self):
        events = [
            {
                "external_id": "1",
                "code": "E001",
                "timestamp": "2026-01-06 08:00:00",
                "direction": "in",
            },
            {
                "external_id": "2",
                "code": "E001",
                "timestamp": "2026-01-06 16:00:00",
                "direction": "out",
            },
        ]
        self._ingest(events, tz="UTC")
        result = self._ingest(events, tz="UTC")
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 2)
        self.assertEqual(self.Punch.search_count([("source", "=", "clock")]), 2)

    def test_cross_batch_pairing(self):
        self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-07 08:00:00",
                    "direction": "in",
                }
            ],
            tz="UTC",
        )
        session = self.Timesheet.search([("employee_id", "=", self.employee.id)])
        self.assertFalse(session.check_out)

        self._ingest(
            [
                {
                    "external_id": "2",
                    "code": "E001",
                    "timestamp": "2026-01-07 17:00:00",
                    "direction": "out",
                }
            ],
            tz="UTC",
        )
        session = self.Timesheet.search([("employee_id", "=", self.employee.id)])
        self.assertEqual(len(session), 1)
        self.assertTrue(session.check_out)
        self.assertAlmostEqual(session.worked_hours, 9.0)

    def test_unknown_code_reported(self):
        result = self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "NOPE",
                    "timestamp": "2026-01-08 08:00:00",
                    "direction": "in",
                }
            ],
            tz="UTC",
        )
        self.assertEqual(result.unknown_codes, ["NOPE"])
        self.assertEqual(result.created, 0)

    def test_invalid_row_collected(self):
        result = self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-09 08:00:00",
                    "direction": "sideways",
                }
            ],
            tz="UTC",
        )
        self.assertEqual(result.created, 0)
        self.assertEqual(len(result.invalid), 1)
        self.assertEqual(result.invalid[0]["index"], 0)

    def test_naive_without_tz_is_invalid(self):
        result = self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-10 08:00:00",
                    "direction": "in",
                }
            ]
        )
        self.assertEqual(result.created, 0)
        self.assertEqual(len(result.invalid), 1)

    def test_timezone_localized_to_utc(self):
        self._ingest(
            [
                {
                    "external_id": "tz1",
                    "code": "E001",
                    "timestamp": "2026-01-05 08:00:00",
                    "direction": "in",
                }
            ],
            tz="America/Toronto",
        )
        punch = self.Punch.search([("external_id", "=", "tz1")])
        self.assertEqual(punch.timestamp, datetime(2026, 1, 5, 13, 0, 0))

    def test_correction_updates_existing_punch(self):
        self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-11 08:00:00",
                    "direction": "in",
                }
            ],
            tz="UTC",
        )
        result = self._ingest(
            [
                {
                    "external_id": "1",
                    "code": "E001",
                    "timestamp": "2026-01-11 09:00:00",
                    "direction": "in",
                }
            ],
            tz="UTC",
        )
        self.assertEqual(result.updated, 1)
        punch = self.Punch.search([("external_id", "=", "1")])
        self.assertEqual(punch.timestamp, datetime(2026, 1, 11, 9, 0, 0))

    def test_schema_rejects_extra_fields(self):
        with self.assertRaises(Exception):  # noqa: B017
            PunchEvent(
                external_id="1",
                code="E001",
                timestamp="2026-01-05 08:00:00",
                direction="in",
                bogus="x",
            )

    def test_source_ref_display_name(self):
        ref = self.env["company.employee.source.ref"].search(
            [("source", "=", "clock"), ("code", "=", "E001")]
        )
        self.assertEqual(ref.display_name, "clock: E001")
