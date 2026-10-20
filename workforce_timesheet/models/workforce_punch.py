from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import api, fields, models
from odoo.exceptions import UserError

from .. import schema

NO_RECOMPUTE = "workforce_timesheet_no_recompute"


class WorkforcePunch(models.Model):
    """A raw, append-only punch event.

    This is the ingestion target for ``workforce_timesheet_{source}`` modules.
    Rows are addressed by ``(source, external_id)`` so periodic batch imports are
    replay-safe: re-ingesting the same batch updates or skips instead of
    duplicating.
    """

    _name = "workforce.punch"
    _description = "Workforce Punch"
    _order = "timestamp, id"

    worker_id = fields.Many2one(
        "workforce.employee",
        required=True,
        ondelete="cascade",
        index=True,
    )
    timestamp = fields.Datetime(required=True, index=True)
    direction = fields.Selection(
        [("in", "In"), ("out", "Out")],
        required=True,
    )
    source = fields.Char(required=True, index=True)
    external_id = fields.Char(required=True)
    device = fields.Char()
    timezone = fields.Char(
        help="IANA timezone the punch was ingested with. Session rebuilds use "
        "it to map the UTC timestamp back to a local work period; punches "
        "without one are grouped in UTC.",
    )
    session_id = fields.Many2one(
        "workforce.timesheet",
        ondelete="set null",
        index=True,
    )
    company_id = fields.Many2one(
        related="worker_id.company_id",
        store=True,
        index=True,
    )

    _source_external_uniq = models.Constraint(
        "unique(source, external_id)",
        "A punch with this source and external id already exists.",
    )

    # ------------------------------------------------------------------
    # Session recomputation hooks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        punches = super().create(vals_list)
        if not self.env.context.get(NO_RECOMPUTE):
            punches.worker_id._recompute_timesheet_sessions()
        return punches

    def write(self, vals):
        employees_before = (
            self.worker_id if "worker_id" in vals else self.env["workforce.employee"]
        )
        result = super().write(vals)
        if not self.env.context.get(NO_RECOMPUTE):
            (employees_before | self.worker_id)._recompute_timesheet_sessions()
        return result

    def unlink(self):
        employees = self.worker_id
        result = super().unlink()
        if not self.env.context.get(NO_RECOMPUTE):
            employees._recompute_timesheet_sessions()
        return result

    # ------------------------------------------------------------------
    # Bulk ingest API
    # ------------------------------------------------------------------
    def _work_period_date(self, start_hour: int):
        """Return the workday ``date`` this punch belongs to.

        The UTC timestamp is converted to the punch's ingest timezone and
        shifted behind the workday start hour, so punches between midnight
        and the start hour count for the previous workday. Unparseable or
        missing timezone values fall back to UTC.
        """
        try:
            tzinfo = ZoneInfo(self.timezone) if self.timezone else timezone.utc
            local = self.timestamp.replace(tzinfo=timezone.utc).astimezone(tzinfo)
        except (ZoneInfoNotFoundError, ValueError, AttributeError):
            local = self.timestamp.replace(tzinfo=timezone.utc)
        return (local - timedelta(hours=start_hour)).date()

    @api.model
    def _get_ingest_schema(self):
        return schema

    @api.model
    def _normalize_timestamp(self, stamp, tz):
        """Return ``(naive_utc_datetime, error)``.

        Aware datetimes are converted to UTC and ``tz`` is ignored. Naive
        datetimes are localized with ``tz``; a naive datetime without ``tz`` is
        rejected rather than stored with a guessed timezone.
        """
        if stamp is None:
            return None, self.env._("Missing timestamp.")
        if stamp.tzinfo is None:
            if not tz:
                return None, self.env._(
                    "Naive timestamp requires a timezone (pass tz=...)."
                )
            try:
                stamp = stamp.replace(tzinfo=ZoneInfo(tz))
            except Exception:
                return None, self.env._("Unknown timezone: %(tz)s", tz=tz)
        return stamp.astimezone(timezone.utc).replace(tzinfo=None), None

    @api.model
    def ingest_punches(self, events, source, *, tz=None):
        """Ingest a batch of standardized punches.

        :param events: iterable of :class:`workforce_timesheet.schema.PunchEvent`
            or equivalent mappings.
        :param str source: the source identifier (must match the
            ``workforce.employee.source.ref.source`` used for the employees).
        :param str tz: IANA timezone used to localize naive timestamps.
        :return: a :class:`workforce_timesheet.schema.IngestResult`.
        """
        schema = self._get_ingest_schema()
        source = (source or "").strip()
        if not source:
            raise UserError(self.env._("A source is required to ingest punches."))

        invalid = []
        validated = []
        for index, event in enumerate(events):
            try:
                if isinstance(event, schema.PunchEvent):
                    punch_event = event
                else:
                    punch_event = schema.PunchEvent.model_validate(event)
            except Exception as exc:
                external_id = (
                    event.get("external_id") if isinstance(event, dict) else None
                )
                invalid.append(
                    {"index": index, "external_id": external_id, "error": str(exc)}
                )
                continue
            validated.append((index, punch_event))

        normalized = []
        for index, punch_event in validated:
            stamp, error = self._normalize_timestamp(punch_event.timestamp, tz)
            if error:
                invalid.append(
                    {
                        "index": index,
                        "external_id": punch_event.external_id,
                        "error": error,
                    }
                )
                continue
            normalized.append((punch_event, stamp))

        codes = {punch_event.code for punch_event, _stamp in normalized}
        refs = self.env["workforce.employee.source.ref"].search(
            [("source", "=", source), ("code", "in", list(codes))]
        )
        employee_by_code = {ref.code: ref.worker_id for ref in refs}
        unknown_codes = sorted(code for code in codes if code not in employee_by_code)

        resolvable = [
            (punch_event, stamp)
            for punch_event, stamp in normalized
            if punch_event.code in employee_by_code
        ]
        external_ids = [punch_event.external_id for punch_event, _stamp in resolvable]
        guarded = self.with_context(**{NO_RECOMPUTE: True})
        existing = {
            punch.external_id: punch
            for punch in guarded.search(
                [("source", "=", source), ("external_id", "in", external_ids)]
            )
        }

        to_create = []
        created = updated = skipped = 0
        affected = self.env["workforce.employee"]
        for punch_event, stamp in resolvable:
            employee = employee_by_code[punch_event.code]
            vals = {
                "worker_id": employee.id,
                "timestamp": stamp,
                "direction": punch_event.direction,
                "source": source,
                "external_id": punch_event.external_id,
                "device": punch_event.device,
                "timezone": tz or None,
            }
            punch = existing.get(punch_event.external_id)
            if punch is None:
                to_create.append(vals)
            elif self._punch_changed(punch, vals):
                punch.write(vals)
                updated += 1
                affected |= employee
            else:
                skipped += 1

        if to_create:
            created_punches = guarded.create(to_create)
            created = len(created_punches)
            affected |= created_punches.worker_id

        sessions_rebuilt = 0
        if affected:
            sessions_rebuilt = self.env["workforce.timesheet"]._recompute_sessions(
                affected
            )

        return schema.IngestResult(
            created=created,
            updated=updated,
            skipped=skipped,
            sessions_rebuilt=sessions_rebuilt,
            unknown_codes=unknown_codes,
            invalid=invalid,
        )

    @api.model
    def _punch_changed(self, punch, vals):
        return (
            punch.worker_id.id != vals["worker_id"]
            or punch.timestamp != vals["timestamp"]
            or punch.direction != vals["direction"]
            or (punch.device or None) != (vals["device"] or None)
            or (punch.timezone or None) != (vals["timezone"] or None)
        )
