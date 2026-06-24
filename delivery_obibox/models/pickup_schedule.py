from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

days = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}


class PickupSchedule(models.Model):
    _name = "obibox.delivery.schedule"
    _description = "Pickup schedule for obibox"

    pickup_day = fields.Selection(
        selection=[
            ("mon", "Monday"),
            ("tue", "Tuesday"),
            ("wed", "Wednesday"),
            ("thu", "Thursday"),
            ("fri", "Friday"),
        ],
        default="mon",
        help="Select the day when the package will be picked up.",
    )
    display_pickup_hour = fields.Integer(
        compute="_compute_display_pickup_hour",
        inverse="_inverse_display_pickup_hour",
        string="Pickup Time",
    )
    pickup_hour = fields.Integer()
    next_pickup = fields.Date(compute="_compute_next_pickup")
    carrier_id = fields.Many2one("delivery.carrier")

    _check_pickup_hour = models.Constraint(
        "CHECK ( pickup_hour >=0 AND pickup_hour <= 23)",
        "Pickup hour must be between 0 and 23",
    )

    @api.model
    def _get_offset(self) -> float:
        user_tz_id = self.env.user.tz or "UTC"
        user_tz = ZoneInfo(user_tz_id)
        return datetime.now(user_tz).utcoffset().total_seconds() / 3600

    @api.depends("pickup_hour")
    def _compute_display_pickup_hour(self):
        for rec in self:
            offset = self._get_offset()
            rec.display_pickup_hour = rec.pickup_hour + offset

    def _inverse_display_pickup_hour(self):
        for rec in self:
            offset = self._get_offset()
            rec.pickup_hour = rec.display_pickup_hour - offset

    @api.depends("pickup_day", "pickup_hour")
    def _compute_next_pickup(self):
        today = datetime.today()
        for rec in self:
            next_pickup_date = today.date() + relativedelta(
                weekday=days[rec.pickup_day]
            )
            if today.date() == next_pickup_date:
                if today.hour >= (rec.pickup_hour):
                    next_pickup_date = next_pickup_date + timedelta(weeks=1)
            rec.next_pickup = next_pickup_date
