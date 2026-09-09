from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.orm.environments import LazyGettext as _

MONTHS_ABBR = {
    1: "JA",
    2: "FE",
    3: "MR",
    4: "AL",
    5: "MA",
    6: "JN",
    7: "JL",
    8: "AU",
    9: "SE",
    10: "OC",
    11: "NO",
    12: "DE",
}


def format_date(date_obj: datetime, format_string: str | None = None) -> str:
    value = ""

    if format_string:
        try:
            if "%q" in format_string:
                code = MONTHS_ABBR.get(date_obj.month)
                format_string = format_string.replace("%q", code)

            value = date_obj.strftime(format_string)
        except ValueError:
            raise ValidationError(
                _(
                    "Could not format date using %(string)s",
                    string=format_string,
                )
            ) from None
    else:
        value = value.isoformat(timespec="seconds")
    return value
