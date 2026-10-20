from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, mute_logger

from odoo.addons.company_timesheet_biostar.models.biostar_backend import BiostarBackend
from odoo.addons.company_timesheet_biostar.models.biostar_client import BiostarAPIError
from odoo.addons.company_timesheet_biostar.models.biostar_mapper import SOURCE

DAY_RECORD = {
    "userId": "10",
    "hidden_dateTime": "2026/10/02",
    "inTime": "08:00:00",
    "outTime": "17:00:00",
}


class _FakeClient:
    """Duck-typed replaceable for BiostarClient behind backend._get_client."""

    def __init__(self, users=(), records=()):
        self.users = list(users)
        self.records = list(records)
        self.report_calls = []
        self.closed = False
        self.fail = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.closed = True
        return None

    def list_users(self, **kwargs):
        if self.fail:
            raise BiostarAPIError("server exploded")
        return self.users

    def get_tna_report(self, user_ids, start_date, end_date, **kwargs):
        self.report_calls.append(((start_date, end_date), tuple(user_ids)))
        return self.records


class TestBiostarBackend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Backend = cls.env["biostar.backend"]
        cls.Employee = cls.env["company.employee"]
        cls.backend = cls.Backend.create(
            {
                "name": "HQ biostar",
                "host": "biostar.local",
                "port": 3002,
                "login_id": "api",
                "password": "secret",
                "tz": "UTC",
                "import_days_back": 2,
            }
        )
        cls.employee = cls.Employee.create({"name": "Bio Worker", "biostar_id": "10"})

    def _fake(self, **state):
        client = _FakeClient(**state)
        patcher = mock.patch.object(BiostarBackend, "_get_client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return client

    # ------------------------------------------------------------------
    # Test connection
    # ------------------------------------------------------------------
    def test_action_error_wrapped_in_usererror(self):
        client = self._fake()
        client.fail = True
        with self.assertRaises(UserError):
            self.backend.action_test_connection()

    # ------------------------------------------------------------------
    # Punch sync
    # ------------------------------------------------------------------
    def test_sync_punches_ingests_and_builds_sessions(self):
        client = self._fake(records=[DAY_RECORD])
        result, report_count = self.backend._sync_punches()
        self.assertEqual((result.created, report_count), (2, 1))
        self.assertEqual(result.sessions_rebuilt, 1)
        session = self.env["company.timesheet"].search(
            [("employee_id", "=", self.employee.id)]
        )
        self.assertEqual(len(session), 1)
        self.assertAlmostEqual(session.worked_hours, 9.0)
        window, ids = client.report_calls[0]
        self.assertIn(10, ids)
        # Window is import_days_back wide, today inclusive.
        (start, end) = window
        self.assertEqual(
            (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days,
            self.backend.import_days_back,
        )

    def test_zero_punch_rows_ingest_nothing(self):
        """Aggregate/title rows pass through without punches and stay silent."""
        client = self._fake(records=[{"isTitle": True, "hidden_user_id": "10"}])
        result, report_count = self.backend._sync_punches()
        self.assertEqual(report_count, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(len(client.report_calls), 1)

    def test_sync_punches_scope_is_backend_company(self):
        other_company = self.env["res.company"].create({"name": "Other Co"})
        foreign = self.Employee.create(
            {"name": "Foreign", "biostar_id": "11", "company_id": other_company.id}
        )
        client = self._fake(records=[])
        self.backend._sync_punches()
        _window, ids = client.report_calls[0]
        self.assertIn(10, ids)  # own employee
        self.assertNotIn(11, ids)  # other company out of scope
        foreign.unlink()

    def test_sync_punches_chunked_by_user(self):
        for index in range(120, 260):
            self.Employee.create({"name": f"Chunk {index}", "biostar_id": str(index)})
        client = self._fake(records=[])
        self.backend._sync_punches()
        chunk_sizes = [len(ids) for (_window, ids) in client.report_calls]
        self.assertEqual(chunk_sizes, [100, 41])  # 140 added + the "10" fixture

    def test_sync_punches_unknown_code_reported(self):
        self._fake(records=[dict(DAY_RECORD, userId="999")])
        result, _count = self.backend._sync_punches()
        self.assertIn("999", result.unknown_codes)
        self.assertEqual(result.created, 0)

    def test_sync_punches_no_linked_employee_is_noop(self):
        client = self._fake(records=[DAY_RECORD])
        lonely = self.Backend.create(
            {
                "name": "Lonely biostar",
                "host": "lonely.local",
                "port": 3002,
                "login_id": "api",
                "password": "secret",
                "tz": "UTC",
                "company_id": self.env["res.company"].create({"name": "Empty Co"}).id,
            }
        )
        result, report_count = lonely._sync_punches()
        self.assertEqual((result.created, report_count), (0, 0))
        self.assertEqual(client.report_calls, [])  # no report requested

    def test_sync_punches_timezone_localizes(self):
        self.backend.tz = "America/Toronto"
        self._fake(records=[dict(DAY_RECORD)])
        result, _count = self.backend._sync_punches()
        self.assertEqual(result.created, 2)
        punch_out = self.env["company.punch"].search(
            [("source", "=", SOURCE), ("direction", "=", "out")],
            limit=1,
        )
        self.assertEqual(punch_out.timestamp, datetime(2026, 10, 2, 21, 0, 0))

    def test_report_window_in_backend_timezone(self):
        self.backend.tz = "America/Toronto"
        start, end = self.backend._report_window()
        today = datetime.now(ZoneInfo("America/Toronto")).date()
        self.assertEqual(end, today.isoformat())
        self.assertEqual(
            datetime.fromisoformat(start).date(),
            today - timedelta(days=self.backend.import_days_back),
        )

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    def test_cron_swallows_api_failure(self):
        client = self._fake()
        client.fail = True
        self.backend._cron_sync()  # must not raise
        self.assertTrue(client.closed)

    # ------------------------------------------------------------------
    # Backend sanity
    # ------------------------------------------------------------------
    def test_get_client_carries_connection_options(self):
        backend = self.Backend.create(
            {
                "name": "Plain HTTP backend",
                "host": "biostar2.local",
                "port": 3002,
                "scheme": "http",
                "verify_ssl": False,
                "login_id": "api",
                "password": "secret",
            }
        )
        client = backend._get_client()
        self.assertEqual(client.scheme, "http")
        self.assertFalse(client.session.verify)
        self.assertEqual(client.base_url, "http://biostar2.local:3002/tna")

    def test_default_client_uses_https_scheme(self):
        client = self.backend._get_client()
        self.assertEqual(client.scheme, "https")
        self.assertTrue(client.session.verify)

    def test_unique_host_port_login(self):
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
        ):
            self.Backend.create(
                {
                    "name": "Duplicate",
                    "host": "biostar.local",
                    "port": 3002,
                    "login_id": "api",
                    "password": "secret",
                }
            )
