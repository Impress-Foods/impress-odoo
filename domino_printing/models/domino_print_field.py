import logging
from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.quality.models.quality import QualityCheck

_logger = logging.getLogger(__name__)


MONTHS_ABRV = {
    "Jan": "JA",
    "Feb": "FE",
    "Mar": "MR",
    "Apr": "AL",
    "May": "MA",
    "Jun": "JN",
    "Jul": "JL",
    "Aug": "AU",
    "Sep": "SE",
    "Oct": "OC",
    "Nov": "NO",
    "Dec": "DE",
}


class DominoPrintField(models.Model):
    _name = "domino.print.field"
    _description = "Domino Print Field Mapping"
    _order = "name"

    name = fields.Char(required=True)
    field_type = fields.Selection(
        [("dynamic", "Dynamic"), ("static", "Static"), ("data", "Data")],
        default="dynamic",
    )
    odoo_field_path = fields.Char(
        help="Odoo field path, e.g. 'product.default_code', 'lot.name'",
    )
    target_field = fields.Char(
        required=True,
        help="Target field name in Domino API payload",
    )
    transform = fields.Char(
        help="Transform to apply, e.g. 'date:%Y-%m-%d', lower'. %q: CAN months abbrv",
    )
    default_value = fields.Char(
        help="Default value if odoo_field_path resolves to empty",
    )

    data_id = fields.Integer()
    data_value = fields.Char()

    required = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    def get_field_value(self, source: QualityCheck):
        self.ensure_one()
        match self.field_type:
            case "dynamic":
                value = source.mapped(self.odoo_field_path)
                if not value:
                    raise ValidationError(
                        self.env._(
                            "No value found for field %(field)s",
                            field=self.target_field,
                        )
                    )
                if len(value) > 1:
                    raise ValidationError(
                        self.env._(
                            "Multiple values found for field %(field)s",
                            field=self.target_field,
                        )
                    )
                return self._transform_value(value[0], self.transform)

            case "data":
                data = {}
                data["name"] = self.target_field
                data["id"] = self.data_id
                data["value"] = self.data_value
                return data

            case _:
                return self.default_value

    @api.model
    def _transform_value(self, value, format: str):
        if not format:
            return value
        if isinstance(value, date | datetime):
            return self._format_date(value, format)
        if format == "upper" and isinstance(value, str):
            return value.upper()
        if format == "lower" and isinstance(value, str):
            return value.lower()
        return value

    @api.model
    def _format_date(self, value: date | datetime, format: str) -> str:
        try:
            if "%q" not in format:
                return value.strftime(format)
            else:
                new_format = format.replace("%q", "%b")
                formatted_date = value.strftime(new_format)
                for month in MONTHS_ABRV:
                    if month in formatted_date:
                        formatted_date = formatted_date.replace(
                            month, MONTHS_ABRV[month]
                        )
                return formatted_date

        except (ValueError, UnicodeError) as err:
            raise ValidationError(
                self.env._(
                    "Could not convert date %(date)s with format %(format)s",
                    date=value,
                    format=format,
                )
            ) from err
