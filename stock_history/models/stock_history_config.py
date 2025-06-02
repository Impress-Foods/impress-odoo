import ast
import logging
from datetime import date, datetime, timedelta

from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE, relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

weekdays = {"mon": MO, "tue": TU, "wed": WE, "thu": TH, "fri": FR, "sat": SA, "sun": SU}
months = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def is_end_of_month(dt: date) -> bool:
    todays_month = dt.month
    tomorrows_month = (dt + timedelta(days=1)).month
    return todays_month != tomorrows_month


def get_end_of_month(month: int) -> date:
    return (
        datetime(day=1, month=month + 1, year=datetime.now().year)
        + relativedelta(days=-1)
    ).date()


class StockHistoryConfig(models.Model):
    _name = "stock.history.config"
    _description = "Stock History Rules"

    name = fields.Char()

    active = fields.Boolean(default=True)
    locked = fields.Boolean(default=False)

    interval_type = fields.Selection(
        [
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
            ("years", "Years"),
            ("day_of_week", "Day of Week"),
            ("day_of_month", "Day of Month"),
            ("day_of_year", "Day of Year"),
            ("end_of_month", "End of Month"),
        ],
        required=True,
    )

    product_domain = fields.Char(default=[])

    duration = fields.Integer(default=1)
    day_of_week = fields.Selection(
        [
            ("mon", "Monday"),
            ("tue", "Tuesday"),
            ("wed", "Wednesday"),
            ("thu", "Thursday"),
            ("fri", "Friday"),
            ("sat", "Saturday"),
            ("sun", "Sunday"),
        ],
        default="mon",
    )

    day_of_month = fields.Integer(string="Day of Month", default=1)
    month_of_year = fields.Selection(
        [
            ("jan", "January"),
            ("feb", "February"),
            ("mar", "March"),
            ("apr", "April"),
            ("may", "May"),
            ("jun", "June"),
            ("jul", "July"),
            ("aug", "August"),
            ("sep", "September"),
            ("oct", "October"),
            ("nov", "November"),
            ("dec", "December"),
        ],
        default="jan",
    )

    last_run = fields.Date()
    next_run = fields.Date(
        compute="_compute_next_run",
        store=True,
        depends=[
            "last_run",
            "interval_type",
            "duration",
            "day_of_week",
            "day_of_month",
            "month_of_year",
        ],
    )

    @api.constrains("day_of_month")
    def _check_day_of_month(self):
        for record in self:
            if record.interval_type == "day_of_month":
                if record.day_of_month < 0 or record.day_of_month > 28:
                    raise ValidationError(
                        _(
                            "Day of month must be between 1 and 28."
                            "Use End of Month option for end of month"
                        )
                    )
            elif record.interval_type == "day_of_year":
                if record.day_of_month < 0 or record.day_of_month > 28:
                    if record.month_of_year:
                        nb_of_days = (
                            datetime(
                                day=1,
                                month=months[record.month_of_year] + 1,
                                year=2025,  # We use 2025 as a standard non-leap year
                            )
                            + relativedelta(days=-1)
                        ).day

                        if record.day_of_month > nb_of_days:
                            raise ValidationError(
                                _(f"Day of month must be between 1 and {nb_of_days}.")
                            )

    @api.constrains("next_run")
    def _check_next_run(self):
        for record in self:
            if record.interval_type in ["days", "weeks", "months", "years"]:
                if record.duration <= 0:
                    raise ValidationError(_("Duration must be greater than 0"))

            elif record.interval_type == "end_of_month" and not is_end_of_month(
                record.next_run
            ):
                raise ValidationError(_("Next run must be at the end of the month"))

    @api.depends(
        "last_run",
        "interval_type",
        "duration",
        "day_of_week",
        "day_of_month",
        "month_of_year",
    )
    def _compute_next_run(self):
        for record in self:
            ref_date = record.last_run or datetime.today().date()
            match record.interval_type:
                case "days":
                    record.next_run = ref_date + relativedelta(days=record.duration)
                case "weeks":
                    record.next_run = ref_date + relativedelta(weeks=record.duration)
                case "months":
                    record.next_run = ref_date + relativedelta(months=record.duration)
                case "years":
                    record.next_run = ref_date + relativedelta(years=record.duration)
                case "day_of_week":
                    next_run = ref_date + relativedelta(
                        weekday=weekdays[record.day_of_week]  # type: ignore
                    )
                    if next_run <= ref_date:
                        next_run = ref_date + relativedelta(
                            weekday=weekdays[record.day_of_week](2)
                        )
                    record.next_run = next_run

                case "day_of_month":
                    next_run = ref_date + relativedelta(day=record.day_of_month)
                    if next_run <= ref_date:
                        next_run = next_run + relativedelta(months=1)
                        next_run = next_run + relativedelta(day=record.day_of_month)
                    record.next_run = next_run

                case "day_of_year":
                    next_run = ref_date + relativedelta(
                        month=months[record.month_of_year], day=record.day_of_month
                    )
                    if next_run <= ref_date:
                        current_year = ref_date.year
                        next_run = next_run + relativedelta(
                            year=current_year + 1,
                            month=months[record.month_of_year],
                            day=record.day_of_month,
                        )
                    record.next_run = next_run

                case "end_of_month":
                    current_month = ref_date.month
                    next_run = get_end_of_month(current_month)
                    if next_run <= ref_date:
                        next_run = get_end_of_month(current_month + 1)

                    record.next_run = next_run

    @api.onchange("interval_type")
    def _handle_day_of_year_day_of_month_change(self):
        if self.interval_type in ["day_of_month"] and self.day_of_month > 28:
            self.day_of_month = 28

    def _create_history(self):
        for record in self:
            record.last_run = datetime.today().date()
            quants = record._get_quants()
            history_group = self.env["stock.history.group"].create(
                {
                    "name": f"{record.name} - {record.last_run}",
                    "history_config_id": record.id,
                    "date": record.last_run,
                }
            )
            quant_values = [
                {
                    "product_id": quant.product_id.id,
                    "quantity": quant.quantity,
                    "uom": quant.product_uom_id.id,
                    "location": quant.location_id.id,
                    "history_group_id": history_group.id,
                }
                for quant in quants
            ]
            self.env["stock.history.line"].create(quant_values)

    def _get_products(self):
        self.ensure_one()
        domain = ast.literal_eval(self.product_domain) or []
        domain.append(("detailed_type", "=", "product"))
        return self.env["product.product"].search(domain)

    def _get_quants(self):
        self.ensure_one()
        return self.env["stock.quant"].search(
            [
                ("product_id", "in", self._get_products().ids),
                ("location_id.usage", "=", "internal"),
            ]
        )

    @api.model
    def cron_create_history(self):
        current_date = datetime.today().date()
        configs = self.env["stock.history.config"].search(
            [("active", "=", True), ("next_run", "<=", current_date)]
        )

        configs._create_history()

    def action_force_run(self):
        self._create_history()

    def action_toggle_lock(self):
        for record in self:
            record.locked = not record.locked
