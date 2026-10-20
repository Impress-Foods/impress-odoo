from odoo import fields, models


class ResCompany(models.Model):
    """Company settings that shape how punches become timesheet sessions."""

    _inherit = "res.company"

    timesheet_day_start_hour = fields.Integer(
        string="Timesheet Day Start",
        default=3,
        help="Work-period boundary hour for timesheet sessions. Punches are "
        "grouped into one session per work period, where a period runs from "
        "this local hour on one day until this hour on the next. A punch"
        " between midnight and this hour belongs to the previous workday, so"
        " overnight shifts ending past midnight stay on their starting"
        " workday.",
    )

    _timesheet_day_start_hour_range = models.Constraint(
        "CHECK(timesheet_day_start_hour >= 0 AND timesheet_day_start_hour <= 23)",
        "The timesheet day start hour must be between 0 and 23.",
    )
