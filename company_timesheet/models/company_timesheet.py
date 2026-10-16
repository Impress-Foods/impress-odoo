from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CompanyTimesheet(models.Model):
    """A work-time session derived purely from :class:`company.punch` events.

    Sessions are never created by hand: they are materialized by
    :meth:`_recompute_sessions`, which walks the punches of an employee in
    chronological order and pairs ``in`` -> ``out``. The rebuild is
    deterministic, so replays, late punches and corrections converge.
    """

    _name = "company.timesheet"
    _description = "Company Timesheet"
    _order = "check_in desc"

    employee_id = fields.Many2one(
        "company.employee",
        required=True,
        ondelete="cascade",
        index=True,
    )
    check_in = fields.Datetime(required=True, index=True)
    check_out = fields.Datetime()
    date = fields.Date(
        compute="_compute_date",
        store=True,
        precompute=True,
        index=True,
    )
    worked_hours = fields.Float(
        compute="_compute_worked_hours",
        store=True,
        aggregator="sum",
    )
    department_id = fields.Many2one(
        related="employee_id.department_id",
        store=True,
        index=True,
    )
    manager_id = fields.Many2one(
        related="employee_id.parent_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="employee_id.company_id",
        store=True,
        index=True,
    )
    punch_ids = fields.One2many(
        "company.punch",
        "session_id",
        string="Punches",
    )

    @api.depends("check_in")
    def _compute_date(self):
        for session in self:
            session.date = session.check_in.date() if session.check_in else False

    @api.depends("check_in", "check_out")
    def _compute_worked_hours(self):
        for session in self:
            if session.check_in and session.check_out:
                delta = session.check_out - session.check_in
                session.worked_hours = delta.total_seconds() / 3600.0
            else:
                session.worked_hours = 0.0

    @api.constrains("employee_id", "check_out")
    def _check_single_open_session(self):
        for session in self.filtered(lambda s: s.check_in and not s.check_out):
            already_open = self.search_count(
                [
                    ("id", "!=", session.id),
                    ("employee_id", "=", session.employee_id.id),
                    ("check_out", "=", False),
                ]
            )
            if already_open:
                raise ValidationError(
                    self.env._(
                        "Employee %(name)s already has an open timesheet session.",
                        name=session.employee_id.display_name,
                    )
                )

    @api.model
    def _recompute_sessions(self, employees):
        """Delete and rebuild the derived sessions for the given employees.

        Returns the number of sessions created.
        """
        employees = employees.exists()
        if not employees:
            return 0
        Timesheet = self.sudo()
        Punch = self.env["company.punch"].sudo()

        Timesheet.search([("employee_id", "in", employees.ids)]).unlink()

        punches = Punch.search(
            [("employee_id", "in", employees.ids)],
            order="employee_id, timestamp, id",
        )
        grouped = {}
        employees_by_id = {}
        for punch in punches:
            grouped.setdefault(punch.employee_id.id, []).append(punch)
            employees_by_id[punch.employee_id.id] = punch.employee_id

        session_vals = []
        session_punches = []
        for employee_id, employee_punches in grouped.items():
            employee = employees_by_id[employee_id]
            open_punch = None
            for punch in employee_punches:
                if punch.direction == "in":
                    # A duplicate ``in`` while a session is open is treated as
                    # dirty data and ignored, so at most one session per
                    # employee stays open (see _check_single_open_session).
                    if open_punch is None:
                        open_punch = punch
                elif open_punch is not None:
                    session_vals.append(self._session_vals(employee, open_punch, punch))
                    session_punches.append(open_punch | punch)
                    open_punch = None
                # An ``out`` without a matching ``in`` is left unlinked.
            if open_punch is not None:
                session_vals.append(self._session_vals(employee, open_punch, None))
                session_punches.append(open_punch)

        if not session_vals:
            return 0

        sessions = Timesheet.create(session_vals)
        for session, punch_set in zip(sessions, session_punches, strict=False):
            punch_set.with_context(company_timesheet_no_recompute=True).write(
                {"session_id": session.id}
            )
        return len(sessions)

    @api.model
    def _session_vals(self, employee, punch_in, punch_out):
        return {
            "employee_id": employee.id,
            "check_in": punch_in.timestamp,
            "check_out": punch_out.timestamp if punch_out else False,
        }
