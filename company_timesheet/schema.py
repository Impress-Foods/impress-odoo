"""Standardized ingest contract for punch batches (public API).

Connector modules (``company_timesheet_{source}``) import from this module, so
treat it as a stable contract: bump ``SCHEMA_VERSION`` on any breaking change.

Example::

    from odoo.addons.company_timesheet.schema import PunchEvent

    events = [
        PunchEvent(
            external_id=row["id"],
            code=row["employee_no"],
            timestamp=row["punch_time"],
            direction=row["kind"],
        )
        for row in rows
    ]
    self.env["company.punch"].ingest_punches(
        events, source="kronos", tz="America/Toronto",
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

PunchDirection = Literal["in", "out"]


class PunchEvent(BaseModel):
    """Single standardized punch produced by a ``company_timesheet_{source}`` module."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    external_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    timestamp: datetime
    direction: PunchDirection
    device: str | None = None


class IngestResult(BaseModel):
    """Outcome of :meth:`company.punch.ingest_punches`."""

    model_config = ConfigDict(extra="forbid")

    created: int = 0
    updated: int = 0
    skipped: int = 0
    sessions_rebuilt: int = 0
    unknown_codes: list[str] = Field(default_factory=list)
    invalid: list[dict] = Field(default_factory=list)
