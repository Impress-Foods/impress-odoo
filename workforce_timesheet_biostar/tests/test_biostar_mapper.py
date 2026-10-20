from odoo.tests.common import TransactionCase

from odoo.addons.workforce_timesheet_biostar.models.biostar_mapper import (
    records_to_punch_events,
)

DAY_ROW = {
    "userId": "10",
    "hidden_dateTime": "2026/10/02",
    "inTime": "08:00:00",
    "outTime": "17:00:00",
}


class TestBiostarMapper(TransactionCase):
    """Translation matrix report row -> standardized punch events.

    Purposely no DB interaction: the mapper contract is what
    ``ingest_punches`` will consume, so these cases pin equivalent semantics:
    naive local datetimes, ``in``/``out`` direction, replay-safe external ids.
    """

    def test_simple_day_yields_in_and_out(self):
        events = records_to_punch_events([DAY_ROW])
        self.assertEqual(len(events), 2)
        first, second = events
        self.assertEqual(first.external_id, "biostar:10:20261002080000:in")
        self.assertEqual(str(first.timestamp), "2026-10-02 08:00:00")
        self.assertEqual(first.direction, "in")
        self.assertEqual(second.external_id, "biostar:10:20261002170000:out")
        self.assertEqual(str(second.timestamp), "2026-10-02 17:00:00")
        self.assertEqual(second.direction, "out")

    def test_title_and_absence_rows_skipped(self):
        title = {"isTitle": True, "hidden_user_id": "1", "datetime": "Admin (1)"}
        absence = {
            "userId": "10",
            "hidden_dateTime": "2026/10/03",
            "exception": "Absence",
        }
        self.assertEqual(records_to_punch_events([title, absence]), [])

    def test_non_dict_rows_ignored(self):
        self.assertEqual(records_to_punch_events([None, "junk"]), [])

    def test_deliberate_next_day_flag(self):
        row = dict(DAY_ROW, isOutTimeNextDay=True)
        (out,) = records_to_punch_events([row])[1:]
        self.assertEqual(str(out.timestamp), "2026-10-03 17:00:00")
        self.assertEqual(out.external_id, "biostar:10:20261003170000:out")

    def test_overnight_out_without_flag_goes_next_day(self):
        row = dict(DAY_ROW, outTime="02:30")
        (out,) = records_to_punch_events([row])[1:]
        self.assertEqual(str(out.timestamp), "2026-10-03 02:30:00")
        self.assertEqual(out.external_id, "biostar:10:20261003023000:out")

    def test_embedded_date_wins_over_flag_arithmetic(self):
        row = {
            "userId": "10",
            "hidden_dateTime": "2026/10/02",
            "inTime": "08:00:00",
            "outTime": "2026/10/03 02:30:00",
        }
        (out,) = records_to_punch_events([row])[1:]
        self.assertEqual(str(out.timestamp), "2026-10-03 02:30:00")

    def test_fallback_day_from_datetime_text(self):
        row = {
            "userId": "10",
            "datetime": "Worker (10 : All) -2026/10/05",
            "inTime": "08:00:00",
            "outTime": "16:00:00",
        }
        events = records_to_punch_events([row])
        self.assertEqual(events[0].external_id, "biostar:10:20261005080000:in")

    def test_in_time_next_day_flag(self):
        # In flagged next day => 10/03 23:30. Out on 10:00 has no flag and is
        # before the in time, so the overnight heuristic shifts it once to the
        # row's next day (10/02 -> 10/03); it stops there deliberately:
        # further juggling belongs to real server data, not to guesses.
        row = dict(DAY_ROW, inTime="23:30", isInTimeNextDay=True, outTime="10:00:00")
        events = records_to_punch_events([row])
        self.assertEqual(str(events[0].timestamp), "2026-10-03 23:30:00")
        self.assertEqual(str(events[1].timestamp), "2026-10-03 10:00:00")

    def test_hidden_user_id_fallback(self):
        row = dict(DAY_ROW, userId="", hidden_user_id="10")
        events = records_to_punch_events([row])
        self.assertEqual(events[0].code, "10")
        self.assertEqual(events[0].external_id, "biostar:10:20261002080000:in")

    def test_out_time_next_day_flag_is_relative_to_row_day(self):
        row = dict(DAY_ROW, isOutTimeNextDay=True)
        (out,) = records_to_punch_events([row])[1:]
        self.assertEqual(str(out.timestamp), "2026-10-03 17:00:00")
        self.assertEqual(out.external_id, "biostar:10:20261003170000:out")

    def test_string_flags_accepted(self):
        row = dict(DAY_ROW, isOutTimeNextDay="true")
        (out,) = records_to_punch_events([row])[1:]
        self.assertEqual(out.external_id, "biostar:10:20261003170000:out")

    def test_untouchable_rows_do_not_raise(self):
        broken = {
            "userId": "10",
            "hidden_dateTime": "2026/13/99",
            "inTime": "not a time",
            "outTime": "08:ou",
        }
        self.assertEqual(records_to_punch_events([broken]), [])

    def test_day_rollup_row_dropped_for_intervals(self):
        """DETAIL adds one first-in/last-out roll-up row per employee-day.

        Keeping it would double-count the day's time, so it is skipped and
        the interval rows feed the punch stream; the roll-up's boundary
        punches also deduplicate against the interval rows' identical ones.
        """
        whole_day = {
            "userId": "6",
            "datetime": "2026/10/19",
            "inTime": "07:33:06",
            "outTime": "16:31:53",
        }
        first_interval = dict(whole_day, outTime="09:16:48")
        last_interval = {
            "userId": "6",
            "datetime": "2026/10/19",
            "inTime": "14:51:14",
            "outTime": "16:31:53",
        }
        events = records_to_punch_events([whole_day, first_interval, last_interval])
        self.assertEqual(
            [event.external_id for event in events],
            [
                "biostar:6:20261019073306:in",
                "biostar:6:20261019091648:out",
                "biostar:6:20261019145114:in",
                "biostar:6:20261019163153:out",
            ],
        )

    def test_single_row_day_is_never_dropped(self):
        """A one-row day keeps its pair even when it spans the full span."""
        events = records_to_punch_events(
            [
                {
                    "userId": "6",
                    "datetime": "2026/10/20",
                    "inTime": "06:54:18",
                    "outTime": "09:58:37",
                }
            ]
        )
        self.assertEqual(
            [(event.direction, str(event.timestamp)) for event in events],
            [("in", "2026-10-20 06:54:18"), ("out", "2026-10-20 09:58:37")],
        )

    def test_is_replayable(self):
        events = records_to_punch_events([DAY_ROW])
        again = records_to_punch_events([dict(DAY_ROW)])
        self.assertEqual(
            [e.external_id for e in events], [e.external_id for e in again]
        )

    # ------------------------------------------------------------------
    # Individual DETAIL row shapes (as returned by /report.json in the
    # field): per-day rows carry enterTime/exitTime instead of inTime/outTime.
    # ------------------------------------------------------------------
    def test_detail_row_enter_and_exit_both_filled(self):
        row = {
            "userId": "6",
            "datetime": "2026/10/19",
            "enterTime": "07:24:00",
            "exitTime": "11:14:24",
        }
        events = records_to_punch_events([row])
        self.assertEqual(len(events), 2)
        first, second = events
        self.assertEqual(first.external_id, "biostar:6:20261019072400:in")
        self.assertEqual(str(first.timestamp), "2026-10-19 07:24:00")
        self.assertEqual(second.external_id, "biostar:6:20261019111424:out")
        self.assertEqual(str(second.timestamp), "2026-10-19 11:14:24")

    def test_detail_row_partial_directions_subset_of_full_pair(self):
        exit_only = {
            "userId": "6",
            "datetime": "     2026/10/19",
            "enterTime": "",
            "exitTime": "11:14:24",
        }
        (out,) = records_to_punch_events([exit_only])
        self.assertEqual(out.direction, "out")
        self.assertEqual(str(out.timestamp), "2026-10-19 11:14:24")

        enter_only = dict(exit_only, enterTime="07:05:00", exitTime="")
        (in_event,) = records_to_punch_events([enter_only])
        self.assertEqual(in_event.direction, "in")
        self.assertEqual(str(in_event.timestamp), "2026-10-19 07:05:00")

    def test_summary_row_dash_placeholders_stay_untouched(self):
        row = {
            "userId": "6",
            "datetime": "2026/10/20",
            "shift": "Menage",
            "inTime": "-",
            "outTime": "-",
        }
        self.assertEqual(records_to_punch_events([row]), [])
