"""Shared X12 element parsing and formatting."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from .outbound import COMPONENT_SEPARATOR, ELEMENT_SEPARATOR, SEGMENT_TERMINATOR

FILE_ENCODING: Final = "cp1252"  # what the framework encodes our files with
DELIMITERS: Final = frozenset(
    {ELEMENT_SEPARATOR, SEGMENT_TERMINATOR, COMPONENT_SEPARATOR}
)
_BLANKS: Final = re.compile(r" {2,}")


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


def _encodable(char: str) -> bool:
    try:
        char.encode(FILE_ENCODING)
    except UnicodeEncodeError:
        return False
    return True


def _is_control(char: str) -> bool:
    """Tabs, line breaks and the like: the file is one line per segment."""
    return unicodedata.category(char)[0] == "C" or char in "\u2028\u2029"


def _transliterate(char: str) -> str:
    """``char`` if the file can hold it, else its closest form, else ``?``."""
    if _encodable(char):
        return char
    plain = "".join(
        part
        for part in unicodedata.normalize("NFKD", char)
        if not unicodedata.combining(part)
    )
    return plain if plain and all(map(_encodable, plain)) else "?"


def clean_text(value: str, width: int) -> str:
    """Free text made safe to write: the delimiters cannot appear in it.

    A delimiter or control character becomes a space, a character the file
    encoding cannot hold is transliterated (``?`` when there is no equivalent),
    runs of spaces are collapsed and the result is cut to ``width``.
    """
    spaced = "".join(
        " " if char in DELIMITERS or _is_control(char) else _transliterate(char)
        for char in value
    )
    return _BLANKS.sub(" ", spaced).strip()[:width]


def check_identifier(value: str, where: str) -> str:
    """``value`` itself, or a ``ValueError`` naming ``where`` if it cannot be written.

    Codes (item numbers, tracking numbers, IDs) must reach the partner as they
    are in Odoo, so they are refused rather than altered.
    """
    bad = sorted(
        {
            char
            for char in value
            if char in DELIMITERS or _is_control(char) or not _encodable(char)
        }
    )
    if bad:
        raise ValueError(
            f"{where} {value!r} holds characters that cannot be written in an "
            f"X12 file: {' '.join(repr(char) for char in bad)}"
        )
    return value
