import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.company_timesheet.models.company_employee_source_ref import (
    CompanyEmployeeSourceRef,
)
from odoo.addons.company_timesheet.schema import IngestResult, PunchEvent

from .biostar_client import (
    BiostarAPIError,
    BiostarClient,
)
from .biostar_mapper import SOURCE, records_to_punch_events

_logger = logging.getLogger(__name__)

# BioStar user ids are numeric strings; /report.json takes them as id strings,
# so the report is requested per chunk of references.
_REPORT_USER_CHUNK = 100


def _tz_get(self):
    return [(tz, tz) for tz in sorted(pytz.common_timezones)]


def _chunks(values: list[int], size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]


class BiostarBackend(models.Model):
    """Connection to a BioStar 2 T&A server feeding company timesheets.

    Employees are linked manually through ``company.employee.biostar_id``;
    this model only stores connection configuration and orchestrates: every
    network call happens in :class:`BiostarClient`, and every punch-pairing
    decision in ``company.timesheet``. It sits between the two.
    """

    _name = "biostar.backend"
    _description = "BioStar 2 Backend"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    host = fields.Char(
        required=True,
        help="BioStar 2 server hostname or address (T&A site, port 3002 by default).",
    )
    port = fields.Integer(required=True, default=3002)
    scheme = fields.Selection(
        selection=[("http", "http"), ("https", "https")],
        required=True,
        default="https",
        help="Protocol the BioStar 2 server listens on. Internal servers "
        "without TLS must use http.",
    )
    verify_ssl = fields.Boolean(
        default=True,
        help="Only used when the scheme is https. Uncheck for servers with a "
        "self-signed TLS certificate.",
    )
    login_id = fields.Char(required=True, help="BioStar 2 API login id.")
    password = fields.Char(required=True, copy=False)
    tz = fields.Selection(
        selection=_tz_get,
        required=True,
        default="UTC",
        string="Timezone",
        help="Timezone of the BioStar server and its devices; report times are "
        "read in this timezone before being converted to UTC.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    import_days_back = fields.Integer(
        default=3,
        help="Rolling window (days) re-imported on every sync; punches are "
        "replay-safe so overlapping windows only update instead of duplicating.",
    )
    linked_employee_count = fields.Integer(
        compute="_compute_linked_employee_count",
        string="Linked Employees",
        help="Employees of this company carrying a BioStar ID.",
    )
    last_punches_sync = fields.Datetime(readonly=True)
    last_connection_check = fields.Datetime(readonly=True)

    _host_port_login_uniq = models.Constraint(
        "unique(host, port, login_id)",
        "This server is already configured with the same API login.",
    )
    _import_days_back_check = models.Constraint(
        "CHECK(import_days_back >= 1)",
        "The import window must cover at least one day.",
    )

    def _compute_linked_employee_count(self):
        for backend in self:
            backend.linked_employee_count = len(
                backend._source_refs().mapped("employee_id")
            )

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_test_connection(self):
        """Login / list users / logout roundtrip to validate configuration."""
        self.ensure_one()
        try:
            with self._get_client() as client:
                total = len(client.list_users())
        except BiostarAPIError as exc:
            raise UserError(
                self.env._("BioStar connection failed: %(error)s", error=exc)
            ) from exc
        self.last_connection_check = fields.Datetime.now()
        return self._notify(
            self.env._("Connection OK"),
            self.env._(
                "The BioStar server responded and listed %(count)s user(s).",
                count=total,
            ),
        )

    def action_sync_punches(self):
        self.ensure_one()
        try:
            result, report_count = self._sync_punches()
        except BiostarAPIError as exc:
            raise UserError(
                self.env._("BioStar sync failed: %(error)s", error=exc)
            ) from exc
        return self._notify(
            self.env._("Punch sync done"),
            self.env._(
                "%(records)s report row(s) fetched, %(events)s punch(es) parsed.\n"
                "Ingestion: %(created)s created, %(updated)s updated, "
                "%(skipped)s skipped; sessions rebuilt: %(sessions)s.\n"
                "Unknown codes: %(unknown)s",
                records=report_count,
                events=result.created + result.updated + result.skipped,
                created=result.created,
                updated=result.updated,
                skipped=result.skipped,
                sessions=result.sessions_rebuilt,
                unknown=", ".join(result.unknown_codes) or "-",
            ),
        )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------
    def _sync_punches(self) -> tuple[IngestResult, int]:
        """Pull the TNA report over the rolling window and ingest it.

        Report rows are translated to naive local punches (no timezone
        guessing here) and fed to the base module's ingest API, which
        localizes with the backend timezone, keeps the ledger replay-safe and
        rebuilds the derived sessions. Returns ``(ingest result, rows fetched)``;
        every intermediate count is logged so a silent zero-import can be
        diagnosed from the server log alone.
        """
        self.ensure_one()
        refs = self._source_refs()
        user_ids = [int(ref.code) for ref in refs if ref.code.isdigit()]
        non_numeric = [ref.code for ref in refs if not ref.code.isdigit()]
        if non_numeric:
            _logger.warning(
                "BioStar backend %s: employees with non-numeric BioStar IDs "
                "cannot be requested in the report: %s",
                self.name,
                ", ".join(sorted(non_numeric)),
            )
        if not user_ids:
            _logger.info(
                "BioStar backend %s: no employee carries a BioStar ID yet.",
                self.name,
            )
            return self._ingest([]), 0

        start_date, end_date = self._report_window()
        with self._get_client() as client:
            records = [
                record
                for chunk in _chunks(user_ids, _REPORT_USER_CHUNK)
                for record in client.get_tna_report(chunk, start_date, end_date)
            ]
            events = records_to_punch_events(records)
        _logger.info(
            "BioStar backend %s: fetched %s report row(s) for %s user id(s) "
            "(%s..%s, individual detail).",
            self.name,
            len(records),
            len(user_ids),
            start_date,
            end_date,
        )
        if records:
            _logger.debug(
                "BioStar backend %s: first report row: %r", self.name, records[0]
            )
        if records and not events:
            _logger.warning(
                "BioStar backend %s: %s report row(s) yielded no punches; the "
                "row shape is unexpected. First row: %r",
                self.name,
                len(records),
                records[0],
            )
        return self._ingest(events), len(records)

    def _ingest(self, events: list[PunchEvent]) -> IngestResult:
        """Ingest standardized punches and stamp the sync timestamp."""
        result = self.env["company.punch"].ingest_punches(
            events, source=SOURCE, tz=self.tz
        )
        self.last_punches_sync = fields.Datetime.now()
        _logger.info(
            "BioStar backend %s punch sync: %s",
            self.name,
            result.model_dump(),
        )
        return result

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync(self) -> None:
        """Sync every active backend; one failing server can't block the rest."""
        for backend in self.search([], limit=100):
            try:
                with self.env.cr.savepoint():
                    backend._sync_punches()
            except Exception:  # cron must never propagate
                _logger.exception("BioStar sync failed for backend %s.", backend.name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_client(self) -> BiostarClient:
        self.ensure_one()
        return BiostarClient(
            self.host,
            self.port,
            self.login_id,
            self.password,
            scheme=self.scheme,
            verify_ssl=self.verify_ssl,
        )

    def _report_window(self) -> tuple[str, str]:
        """``(start, end)`` report dates (``YYYY-MM-DD``) in the backend tz.

        BioStar report boundaries are dates in the server timezone, matching
        how the TNA report keys its rows.
        """
        tzinfo = pytz.timezone(self.tz) if self.tz else pytz.utc
        today = pytz.utc.localize(fields.Datetime.now()).astimezone(tzinfo).date()
        return (
            (today - timedelta(days=max(self.import_days_back or 1, 1))).isoformat(),
            today.isoformat(),
        )

    def _source_refs(self) -> "CompanyEmployeeSourceRef":
        """``biostar`` references of employees belonging to this backend.

        References are derived from ``company.employee.biostar_id`` and carry
        the employee's company, so scoping on it keeps multi-company setups
        honest: a backend never imports punches of another company's people.
        """
        self.ensure_one()
        return self.env["company.employee.source.ref"].search(
            [("source", "=", SOURCE), ("company_id", "=", self.company_id.id)]
        )

    def _notify(self, title: str, message: str) -> dict:
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": title, "message": message, "sticky": False},
        }
