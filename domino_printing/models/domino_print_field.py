import logging
import re
from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.quality.models.quality import QualityCheck

_logger = logging.getLogger(__name__)


class DominoPrintField(models.Model):
    _name = "domino.print.field"
    _description = "Domino Print Field Mapping"
    _order = "name"

    # Abbreviations for %q format directive
    months_abbreviations = {
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
        help="Transform to apply, e.g. 'date: %Y-%m-%d', lower'. %q: CAN months abbrv",
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
                result = value[0]
                if not result:
                    if self.default_value:
                        return self.default_value
                    raise ValidationError(
                        self.env._(
                            "No value found for field %(field)s",
                            field=self.target_field,
                        )
                    )
                return self._transform_value(result, self.transform)

            case "data":
                data = {}
                data["name"] = self.target_field
                data["id"] = self.data_id
                data["value"] = self.data_value
                return data

            case _:
                return self.default_value

    @api.model
    def _transform_value(self, value, fmt: str):
        if not fmt:
            return value
        if isinstance(value, date | datetime):
            return self._format_date(value, fmt)
        if fmt == "upper" and isinstance(value, str):
            return value.upper()
        if fmt == "lower" and isinstance(value, str):
            return value.lower()
        return value

    @api.model
    def _format_date(self, value: date | datetime, fmt: str) -> str:
        try:
            if "%q" not in fmt:
                return value.strftime(fmt)
            new_format = fmt.replace("%q", "%b")
            formatted_date = value.strftime(new_format)
            for abrv, can_abrv in self.months_abbreviations.items():
                formatted_date = re.sub(rf"\b{abrv}\b", can_abrv, formatted_date)
            return formatted_date

        except (ValueError, UnicodeError) as err:
            raise ValidationError(
                self.env._(
                    "Could not convert date %(date)s with format %(fmt)s",
                    date=value,
                    fmt=fmt,
                )
            ) from err
