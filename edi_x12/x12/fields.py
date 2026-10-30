"""Shared X12 element parsing and formatting."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def parse_decimal(text: str, where: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError(f"{where} is not a number: {text!r}") from error


def parse_date(text: str, where: str) -> date:
    """A CCYYMMDD date."""
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except (ValueError, IndexError) as error:
        raise ValueError(f"{where} is not a CCYYMMDD date: {text!r}") from error


def format_quantity(value: Decimal) -> str:
    """Plain decimal text: ``5`` not ``5.0``."""
    return format(value.normalize(), "f")


def format_date(value: date | datetime) -> str:
    """CCYYMMDD."""
    return value.strftime("%Y%m%d")


def format_time(value: datetime) -> str:
    """HHMM."""
    return value.strftime("%H%M")


def time_code(moment: datetime) -> str:
    """DTM04: the UTC offset of ``moment`` as an X12 time code (ID, 2 characters).

    East of UTC the code is the offset in hours (01 to 12). West of it the code
    is 25 minus the hours: 20 is UTC-5, 21 is UTC-4 and 16 is UTC-9, as in the
    buyer's guide and samples. UTC itself is UT.
    """
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError("a shipping time needs a time zone")
    minutes = int(offset.total_seconds() // 60)
    if minutes == 0:
        return "UT"
    if minutes % 60:
        raise ValueError("only whole-hour UTC offsets have an X12 time code")
    hours = minutes // 60
    return f"{hours:02d}" if hours > 0 else f"{25 + hours:02d}"
