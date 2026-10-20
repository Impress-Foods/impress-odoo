from datetime import date, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .workforce_punch import NO_RECOMPUTE


class WorkforceTimesheet(models.Model):
    """A work-time session derived purely from :class:`workforce.punch` events.

    Sessions are never created by hand: they are materialized by
    :meth:`_recompute_sessions`, which groups punches into work periods (one
    per workday, bounded by the company's local start hour) and turns each
    period into a first-in/last-out session. The rebuild is deterministic,
    so replays, late punches and corrections converge.
    """

    _name = "workforce.timesheet"
    _description = "Workforce Timesheet"
    _order = "check_in desc"

    worker_id = fields.Many2one(
        "workforce.employee",
        required=True,
        ondelete="cascade",
        index=True,
    )
    check_in = fields.Datetime(required=True, index=True)
    check_out = fields.Datetime()
    date = fields.Date(
        compute="_compute_date",
        store=True,
        index=True,
    )
    timezone = fields.Char(
        help="Ingest timezone of the punch that opened this session, used to "
        "localize its workday. Manually created sessions fall back to UTC.",
    )
    worked_hours = fields.Float(
        compute="_compute_worked_hours",
        store=True,
        aggregator="sum",
        help="Sum of the session's in→out interval durations. Unpaid gaps "
        "between intervals (breaks) are excluded, matching BioStar's Total "
        "work time; the first-in/last-out span is visible through check_in "
        "and check_out.",
    )
    department_id = fields.Many2one(
        related="worker_id.department_id",
        store=True,
        index=True,
    )
    manager_id = fields.Many2one(
        related="worker_id.parent_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="worker_id.company_id",
        store=True,
        index=True,
    )
    punch_ids = fields.One2many(
        "workforce.punch",
        "session_id",
        string="Punches",
    )

    @api.depends(
        "check_in",
        "timezone",
        "company_id.timesheet_day_start_hour",
    )
    def _compute_date(self):
        """The workday the session belongs to, not the UTC day of check_in.

        Localizes check_in with the session's ingest timezone (manually
        created sessions have none and fall back to UTC) and shifts behind
        the company's boundary hour, so a night shift starting before the
        local boundary keeps the previous day's date.
        """
        for session in self:
            if not session.check_in:
                session.date = False
                continue
            try:
                tzinfo = (
                    ZoneInfo(session.timezone) if session.timezone else timezone.utc
                )
                local = session.check_in.replace(tzinfo=timezone.utc).astimezone(tzinfo)
            except (ZoneInfoNotFoundError, ValueError):
                local = session.check_in
            start_hour = session.company_id.sudo().timesheet_day_start_hour
            session.date = (local - timedelta(hours=start_hour)).date()

    @api.depends("punch_ids.timestamp", "punch_ids.direction")
    def _compute_worked_hours(self):
        """Sum of in→out interval durations, unpaid gaps excluded.

        Walks the linked punches chronologically: the first ``in`` opens an
        interval, the next ``out`` closes it and adds its duration. Gaps
        between intervals (breaks) and orphan ``out``s contribute nothing,
        so the result matches BioStar's Total work time rather than the
        first-in/last-out span (which is still visible through ``check_in``
        /``check_out``). A stale punch (an ``out`` before the opened ``in``)
        is skipped rather than subtracting.
        """
        for session in self:
            worked = 0.0
            open_in = None
            for punch in session.punch_ids.sorted("timestamp"):
                if punch.direction == "in":
                    if open_in is None:
                        open_in = punch.timestamp
                elif open_in is not None and punch.timestamp > open_in:
                    worked += (punch.timestamp - open_in).total_seconds() / 3600.0
                    open_in = None
            session.worked_hours = worked

    @api.constrains("worker_id", "check_out")
    def _check_single_open_session(self):
        for session in self.filtered(lambda s: s.check_in and not s.check_out):
            already_open = self.search_count(
                [
                    ("id", "!=", session.id),
                    ("worker_id", "=", session.worker_id.id),
                    ("check_out", "=", False),
                ]
            )
            if already_open:
                raise ValidationError(
                    self.env._(
                        "Employee %(name)s already has an open timesheet session.",
                        name=session.worker_id.display_name,
                    )
                )

    @api.model
    def _recompute_sessions(self, employees):
        """Delete and rebuild the derived sessions for the given employees.

        Punches are grouped into work periods: one period per workday, where
        the workday runs from the company's local start hour
        (:attr:`res.company.timesheet_day_start_hour`, default 3AM) until the
        same hour the next day. A period's session spans its first ``in`` to
        its last ``out``; every punch of the period is linked to the session.
        The rebuild is deterministic, so replays, late punches and
        corrections converge.

        Returns the number of sessions created.
        """
        employees = employees.exists()
        if not employees:
            return 0
        Timesheet = self.sudo()
        Punch = self.env["workforce.punch"].sudo()

        Timesheet.search([("worker_id", "in", employees.ids)]).unlink()

        punches = Punch.search(
            [("worker_id", "in", employees.ids)],
            order="worker_id, timestamp, id",
        )
        grouped = {}
        employees_by_id = {}
        for punch in punches:
            grouped.setdefault(punch.worker_id.id, []).append(punch)
            employees_by_id[punch.worker_id.id] = punch.worker_id

        session_vals = []
        session_punches = []
        for worker_id, employee_punches in grouped.items():
            employee = employees_by_id[worker_id]
            for check_in, check_out, period_punches in self._worker_work_periods(
                employee, employee_punches
            ):
                session_vals.append(self._session_vals(employee, check_in, check_out))
                session_punches.append(period_punches)

        if not session_vals:
            return 0

        sessions = Timesheet.create(session_vals)
        for session, punch_set in zip(sessions, session_punches, strict=False):
            punch_set.with_context(**{NO_RECOMPUTE: True}).write(
                {"session_id": session.id}
            )
        return len(sessions)

    def _worker_work_periods(self, employee, punches):
        """Yield ``(check_in, check_out, punches)`` per work period.

        A work period covers one workday between two local
        ``timesheet_day_start_hour`` boundaries (3AM by default): punches up
        to that hour belong to the previous workday. A session opens with a
        period's first ``in``; it closes at that period's last ``out`` -
        unless the period's latest punch is an ``in``, which means the shift
        is still running (or its ``out`` slipped into a later work period);
        the next period then either provides the closing ``out`` or keeps
        the session open. Middle punches stay linked to the session for
        traceability. An ``in`` while a session is already open is ignored,
        and an orphan ``out`` before any ``in`` is left unlinked, matching
        the raw ledger's dirty-data tolerance.
        """
        start_hour = employee.company_id.sudo().timesheet_day_start_hour
        periods: dict[date, list[Any]] = {}
        for punch in punches:
            periods.setdefault(punch._work_period_date(start_hour), []).append(punch)

        Punch = self.env["workforce.punch"].sudo()
        check_in = None
        period_punches: list[Any] = []
        for _period_date, group in sorted(periods.items()):
            if check_in is None:
                check_in = next(
                    (punch for punch in group if punch.direction == "in"), None
                )
                if check_in is None:
                    continue
                period_punches = list(group)
            else:
                # The session opened on an earlier workday; absorb this one.
                period_punches.extend(group)
            # The session closes at the group's last ``out`` - but only when
            # the group does not end with an ``in``: a trailing ``in`` means
            # the shift is still running (its ``out`` must arrive with a
            # later sync, possibly past the workday boundary).
            last_punch = group[-1] if group else None
            check_out = next(
                (
                    punch
                    for punch in reversed(group)
                    if punch.direction == "out" and punch.timestamp > check_in.timestamp
                ),
                None,
            )
            if last_punch is not None and last_punch.direction == "in":
                # Still running: its closing ``out`` arrives with a later
                # sync (possibly in a later work period).
                continue
            if check_out is not None:
                yield check_in, check_out, Punch.concat(*period_punches)
                check_in = None
                period_punches = []
        if check_in is not None:
            yield check_in, None, Punch.concat(*period_punches)

    @api.model
    def _session_vals(self, employee, punch_in, punch_out):
        return {
            "worker_id": employee.id,
            "check_in": punch_in.timestamp,
            "check_out": punch_out.timestamp if punch_out else False,
            "timezone": punch_in.timezone,
        }
