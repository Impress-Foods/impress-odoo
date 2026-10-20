"""Translate BioStar 2 TNA report rows (Individual DETAIL) into punches.

The functions here are pure: no Odoo imports, no I/O. Report times are naive
local datetimes in the BioStar server/device timezone (chosen on the backend);
the conversion to UTC is centralized in ``workforce.punch.ingest_punches``
through its ``tz`` argument, so nothing here guesses timezones.

Row shapes confirmed against a live DETAIL response:

* title rows (``isTitle``) and absence-only rows carry no punch and are
  skipped rather than reported as invalid noise,
* the day is taken from ``hidden_dateTime`` (``YYYY/MM/DD``) and falls back
  on the first date found inside the ``datetime`` text,
* times accept ``HH:MM[:SS]`` (plus an ``( HH:MM:SS )`` rendering suffix) or
  a full ``YYYY[-/]MM[-/]DD HH:MM[:SS]`` value whose own date wins over the
  row day; SUMMARY-flavoured rows say ``inTime``/``outTime``, DETAIL interval
  rows say ``enterTime``/``exitTime`` - both pairs are accepted,
* the ``isInTimeNextDay``/``isOutTimeNextDay`` flags shift an event by one
  day; without a flag, an out-time not later than the in-time is treated as
  the next day (overnight shift),
* each employee-day also carries one roll-up row (first entry -> last exit)
  in addition to the per-interval rows. The roll-up is dropped here: keeping
  both would double-count the day's time. When the interval rows cover the
  same span, the roll-up row is redundant by construction.

External id stability
    ``external_id`` keys embed the punch timestamp at second precision
    (``(user, stamp, direction)``), which stays unique across the many
    same-day punches DETAIL yields and makes re-imports converge to
    ``updated``/``skipped`` at :meth:`workforce.punch.ingest_punches` instead
    of duplicating rows. Identical punches appearing on several rows (for
    example a shared shift boundary) are emitted once.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from odoo.addons.workforce_timesheet.schema import PunchEvent

SOURCE = "biostar"

_DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")


@dataclass(frozen=True)
class _Row:
    """One parsed report row: a punch interval (either side may be absent)."""

    code: str
    day: date
    in_stamp: datetime | None
    out_stamp: datetime | None


def records_to_punch_events(records: Iterable[dict[str, Any]]) -> list[PunchEvent]:
    """Convert raw TNA ``records`` rows into standardized punches.

    Rows without a resolvable user code, day, or punch time (title rows,
    absence rows, corrupted rows) are skipped: they carry no punch, and
    flooding ``invalid`` with unparseable titles would bury real problems.
    Unrecognized user codes are surfaced by ``ingest_punches`` as
    ``unknown_codes`` regardless.
    """
    parsed = [
        row
        for row in (
            _parse_row(record) for record in records if isinstance(record, dict)
        )
        if row is not None
    ]
    for roll_up in _roll_up_rows(parsed):
        parsed.remove(roll_up)

    events: list[PunchEvent] = []
    seen: set[str] = set()
    for row in parsed:
        for stamp, direction in (
            (row.in_stamp, "in"),
            (row.out_stamp, "out"),
        ):
            if stamp is None:
                continue
            event = _event(row.code, stamp, direction)
            if event.external_id in seen:
                continue
            seen.add(event.external_id)
            events.append(event)
    return events


def _roll_up_rows(rows: list[_Row]) -> list[_Row]:
    """Rows that only restate a whole employee-day span (first entry/last exit).

    A DETAIL response lists one roll-up row per employee-day plus the real
    interval rows. A row is a roll-up when it starts at the day's earliest
    entry and ends at its latest exit while at least one sibling row exists;
    dropping it keeps the day's working time from counting twice.
    """
    roll_ups: list[_Row] = []
    groups: dict[tuple[str, date], list[_Row]] = {}
    for row in rows:
        groups.setdefault((row.code, row.day), []).append(row)
    for group_rows in groups.values():
        if len(group_rows) < 2:
            # Nothing to be redundant against: the single row is the report.
            continue
        ins = [row.in_stamp for row in group_rows if row.in_stamp is not None]
        outs = [row.out_stamp for row in group_rows if row.out_stamp is not None]
        if not ins or not outs:
            continue
        first_in, last_out = min(ins), max(outs)
        roll_ups.extend(
            row
            for row in group_rows
            if row.in_stamp == first_in and row.out_stamp == last_out
        )
    return roll_ups


def _parse_row(record: dict[str, Any]) -> _Row | None:
    """Parse one report row; ``None`` for rows carrying no usable punch."""
    code = str(record.get("userId") or record.get("hidden_user_id") or "").strip()
    day = _parse_date(record.get("hidden_dateTime"), record.get("datetime"))
    if not code or day is None:
        return None

    in_time = record.get("inTime")
    if not _has_stamp_text(in_time):
        # DETAIL interval rows name the punches enterTime/exitTime.
        in_time = record.get("enterTime")
    out_time = record.get("outTime")
    if not _has_stamp_text(out_time):
        out_time = record.get("exitTime")
    in_stamp, in_embedded = _parse_stamp(day, in_time)
    out_stamp, out_embedded = _parse_stamp(day, out_time)

    if in_stamp is not None and _flag(record, "isInTimeNextDay") and not in_embedded:
        in_stamp += timedelta(days=1)
    if out_stamp is not None and not out_embedded:
        if _flag(record, "isOutTimeNextDay") or (
            in_stamp is not None and out_stamp <= in_stamp
        ):
            out_stamp += timedelta(days=1)

    if in_stamp is None and out_stamp is None:
        return None
    return _Row(code=code, day=day, in_stamp=in_stamp, out_stamp=out_stamp)


def _has_stamp_text(value: Any) -> bool:
    """True when the value is a non-empty stamp other than a '-' placeholder."""
    return bool(value) and str(value).strip() not in ("", "-")


def _event(code: str, stamp: datetime, direction: str) -> PunchEvent:
    return PunchEvent(
        external_id=f"{SOURCE}:{code}:{stamp:%Y%m%d%H%M%S}:{direction}",
        code=code,
        timestamp=stamp,
        direction=direction,
        device=None,
    )


def _parse_date(*candidates: Any) -> date | None:
    """First ``YYYY-M-D``/``YYYY/M/D`` date found in the candidate values."""
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        match = _DATE_RE.search(candidate)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                continue
    return None


def _parse_stamp(day: date, stamped: Any) -> tuple[datetime | None, bool]:
    """Combine ``day`` with a time value.

    Returns ``(stamp, owns_date)``; a time value carrying its own date wins
    over ``day`` (``owns_date=True``). Times that do not parse are ``(None,
    False)`` so the caller can skip the punch rather than invent one.
    """
    if not isinstance(stamped, str):
        return None, False
    date_match = _DATE_RE.match(stamped.lstrip())
    if date_match:
        year, month, day_of_stamp = (int(part) for part in date_match.groups())
        try:
            day = date(year, month, day_of_stamp)
        except ValueError:
            return None, False
        owns_date = True
    else:
        owns_date = False
    time_match = _TIME_RE.search(stamped)
    if not time_match:
        return None, False
    hour, minute, second = (int(part or 0) for part in time_match.groups())
    try:
        return datetime.combine(day, time(hour, minute, second)), owns_date
    except ValueError:
        return None, False


def _flag(record: dict[str, Any], key: str) -> bool:
    value = record.get(key)
    return value is True or str(value).strip().lower() in ("true", "1")
