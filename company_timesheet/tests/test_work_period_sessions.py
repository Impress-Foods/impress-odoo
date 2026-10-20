from datetime import datetime

from odoo.tests.common import TransactionCase


class TestWorkPeriodSessions(TransactionCase):
    """Whole-workday session grouping with the configurable boundary hour.

    Punches are stored in UTC; tests use a fixed-offset timezone without DST
    (Asia/Tokyo, UTC+9) to keep the local conversions predictable. Default
    boundary hour is 3 (a work period runs 03:00 day N -> 02:59 day N+1).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Punch = cls.env["company.punch"]
        cls.Timesheet = cls.env["company.timesheet"]
        cls.employee = cls.env["company.employee"].create({"name": "Shifter"})

    def _punch(self, direction, timestamp, external_id, timezone=None):
        return self.Punch.create(
            {
                "employee_id": self.employee.id,
                "timestamp": timestamp,
                "direction": direction,
                "source": "test",
                "external_id": external_id,
                "timezone": timezone,
            }
        )

    def _sessions(self, employee=None):
        return self.Timesheet.search(
            [("employee_id", "=", (employee or self.employee).id)]
        )

    def test_intervals_merge_into_one_period_session(self):
        self._punch("in", datetime(2026, 2, 2, 8, 0), "m1")
        self._punch("out", datetime(2026, 2, 2, 12, 0), "m2")
        self._punch("in", datetime(2026, 2, 2, 13, 0), "m3")
        self._punch("out", datetime(2026, 2, 2, 17, 0), "m4")

        sessions = self._sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            (sessions.check_in, sessions.check_out),
            (datetime(2026, 2, 2, 8, 0), datetime(2026, 2, 2, 17, 0)),
        )
        self.assertAlmostEqual(sessions.worked_hours, 9.0)
        self.assertEqual(len(sessions.punch_ids), 4)

    def test_consecutive_days_stay_separate_sessions(self):
        self._punch("in", datetime(2026, 2, 2, 8, 0), "c1")
        self._punch("out", datetime(2026, 2, 2, 17, 0), "c2")
        self._punch("in", datetime(2026, 2, 3, 8, 0), "c3")
        self._punch("out", datetime(2026, 2, 3, 17, 0), "c4")

        sessions = self._sessions().sorted("check_in")
        self.assertEqual(len(sessions), 2)
        self.assertEqual(
            list(sessions.mapped("date")),
            [datetime(2026, 2, 2).date(), datetime(2026, 2, 3).date()],
        )

    def test_punches_before_start_hour_belong_previous_workday(self):
        """01:00 and 02:00 local (Asia/Tokyo) still count for the day before."""
        # Local Oct 1 09:00 -> UTC Oct 1 00:00; local Oct 1 17:30 -> 08:30.
        self._punch("in", datetime(2026, 10, 1, 0, 0), "b1", timezone="Asia/Tokyo")
        self._punch("out", datetime(2026, 10, 1, 8, 30), "b2", timezone="Asia/Tokyo")
        # Local Oct 2 01:00 -> UTC Oct 1 16:00; still workday Oct 1.
        self._punch("in", datetime(2026, 10, 1, 16, 0), "b3", timezone="Asia/Tokyo")
        # Local Oct 2 02:59 -> UTC Oct 1 17:59; still workday Oct 1.
        self._punch("out", datetime(2026, 10, 1, 17, 59), "b4", timezone="Asia/Tokyo")
        # Local Oct 2 09:00 -> UTC Oct 2 00:00; new workday.
        self._punch("in", datetime(2026, 10, 2, 0, 0), "b5", timezone="Asia/Tokyo")
        self._punch("out", datetime(2026, 10, 2, 2, 0), "b6", timezone="Asia/Tokyo")

        sessions = self._sessions().sorted("check_in")
        self.assertEqual(len(sessions), 2)
        self.assertEqual(
            (sessions[0].check_in, sessions[0].check_out),
            (datetime(2026, 10, 1, 0, 0), datetime(2026, 10, 1, 17, 59)),
        )
        self.assertEqual(len(sessions[0].punch_ids), 4)
        self.assertEqual(
            (sessions[1].check_in, sessions[1].check_out),
            (datetime(2026, 10, 2, 0, 0), datetime(2026, 10, 2, 2, 0)),
        )

    def test_shift_crossing_boundary_stays_on_starting_workday(self):
        """An out after the boundary hour closes the open period's session."""
        self._punch("in", datetime(2026, 10, 1, 22, 0), "x1")  # workday Oct 1
        self._punch("out", datetime(2026, 10, 2, 4, 0), "x2")  # past 3AM: Oct 2

        sessions = self._sessions().sorted("check_in")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            (sessions[0].date, sessions[0].check_in, sessions[0].check_out),
            (
                datetime(2026, 10, 1).date(),
                datetime(2026, 10, 1, 22, 0),
                datetime(2026, 10, 2, 4, 0),
            ),
        )
        self.assertAlmostEqual(sessions[0].worked_hours, 6.0)
        self.assertEqual(len(sessions[0].punch_ids), 2)

    def test_company_boundary_hour_is_honored(self):
        self.env.company.timesheet_day_start_hour = 5
        self._punch("in", datetime(2026, 10, 1, 22, 0), "h1")
        self._punch("out", datetime(2026, 10, 2, 4, 30), "h2")
        self._punch("in", datetime(2026, 10, 2, 9, 0), "h3")
        self._punch("out", datetime(2026, 10, 2, 17, 0), "h4")

        # 04:30 is before the 5AM boundary: still workday Oct 1.
        sessions = self._sessions().sorted("check_in")
        self.assertEqual(len(sessions), 2)
        self.assertEqual(
            (sessions[0].check_in, sessions[0].check_out),
            (datetime(2026, 10, 1, 22, 0), datetime(2026, 10, 2, 4, 30)),
        )
        self.assertEqual(
            (sessions[1].check_in, sessions[1].check_out),
            (datetime(2026, 10, 2, 9, 0), datetime(2026, 10, 2, 17, 0)),
        )

    def test_unclosed_in_is_the_only_open_session(self):
        self._punch("in", datetime(2026, 2, 2, 8, 0), "o1")
        self._punch("out", datetime(2026, 2, 2, 16, 0), "o2")
        self._punch("in", datetime(2026, 2, 3, 8, 0), "o3")
        self._punch("in", datetime(2026, 2, 3, 9, 0), "o4")

        sessions = self._sessions().sorted("check_in")
        self.assertEqual(len(sessions), 2)
        self.assertEqual(
            (sessions[0].check_in, sessions[0].check_out),
            (datetime(2026, 2, 2, 8, 0), datetime(2026, 2, 2, 16, 0)),
        )
        self.assertEqual(sessions[1].check_in, datetime(2026, 2, 3, 8, 0))
        self.assertFalse(sessions[1].check_out)

    def test_session_date_follows_work_period_not_utc(self):
        """The session date is the starting workday in local time.

        America/Bogota (UTC-5): local Oct 1 22:00 is stored as UTC Oct 2
        03:00, so a naive ``check_in.date()`` would give the wrong day.
        """
        self._punch("in", datetime(2026, 10, 2, 3, 0), "d1", timezone="America/Bogota")
        self._punch("out", datetime(2026, 10, 2, 8, 0), "d2", timezone="America/Bogota")

        session = self._sessions()
        self.assertEqual(
            (session.check_in, session.date),
            (datetime(2026, 10, 2, 3, 0), datetime(2026, 10, 1).date()),
        )

    def test_orphan_out_before_any_in_is_ignored(self):
        self._punch("out", datetime(2026, 2, 2, 12, 0), "r1")
        self.assertEqual(len(self._sessions()), 0)
        self.assertFalse(self._sessions())
