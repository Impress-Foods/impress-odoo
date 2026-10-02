from datetime import date, datetime

from odoo.exceptions import ValidationError
from odoo.tools.translate import LazyTranslate

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


def format_date(date_obj: date | datetime, format_string: str | None = None) -> str:
    """Format an Odoo date value, including the Canadian month code ``%q``."""
    value = ""
    if format_string:
        try:
            normalized_format = format_string
            if "%q" in normalized_format:
                code = MONTHS_ABBR[date_obj.month]
                normalized_format = normalized_format.replace("%q", code)
            value = date_obj.strftime(normalized_format)
        except (KeyError, ValueError) as error:
            raise ValidationError(
                LazyTranslate(
                    "Could not format date using %(format)s", format=format_string
                )
            ) from error
    else:
        if isinstance(date_obj, datetime):
            value = date_obj.isoformat(timespec="seconds")
        else:
            value = date_obj.isoformat()
    return value
