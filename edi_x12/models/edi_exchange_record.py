import logging
from collections.abc import Callable

from psycopg2 import IntegrityError, OperationalError

from odoo import api, fields, models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.addons.integration_queue_job.job import identity_exact

from ..x12.reading import document_sets

_logger = logging.getLogger(__name__)


FUNCTIONAL_ACKNOWLEDGMENT = "FA"
IN_JOB = "x12_in_job"  # context key: the work is being done by a queue job
BLOCKED_RETRY_SECONDS = 60
SEND_JOB = "x12_send_job"
JOB_WAITING_STATES = ("wait_dependencies", "pending", "enqueued", "started")


class EdiExchangeRecord(models.Model):
    _inherit = "edi.exchange.record"

    x12_control_number = fields.Char(
        string="X12 control number",
        index=True,
        copy=False,
        readonly=True,
        help="Interchange control number (ISA13) of the file we sent. The "
        "partner's acknowledgment refers to the file by it.",
    )
    x12_document = fields.Char(
        string="X12 document",
        copy=False,
        readonly=True,
        help="Transaction set the file holds, for example 850 or 997.",
    )

    x12_is_x12 = fields.Boolean(
        string="On an X12 backend",
        compute="_compute_x12_is_x12",
    )

    @api.depends("backend_id.backend_type_id")
    def _compute_x12_is_x12(self) -> None:
        x12_type = self.env.ref("edi_x12.edi_backend_x12")
        for record in self:
            record.x12_is_x12 = record.backend_id.backend_type_id == x12_type

    def _job_retry_params(self) -> dict:
        """Keyword arguments of the retryable error raised by a failed upload.

        ``edi.backend.exchange_send`` asks the record for them. Only
        ``edi_queue_oca`` defines the method, and it is not used here.
        """
        return {}

    def action_exchange_send(self):
        """Extends edi.exchange.record.action_exchange_send.

        The files of an X12 backend are uploaded by a job, never inside the
        transaction that asked for it: if that transaction rolls back after the
        upload, the partner would hold a file Odoo has no trace of. The job row
        is committed with the transaction, so it exists only if the work does.
        The job itself comes back here with ``IN_JOB`` set and does the upload.
        """
        self.ensure_one()
        if not self.x12_is_x12 or self.env.context.get(IN_JOB):
            return super().action_exchange_send()
        self.with_delay(identity_key=identity_exact).x12_send_job()
        return None

    def action_exchange_receive_process_chained(self):
        """Extends edi.exchange.record.action_exchange_receive_process_chained.

        Each file of an X12 backend is received and processed by its own job, so
        a file that fails does not roll back the others of the same run.
        """
        if not self.x12_is_x12 or self.env.context.get(IN_JOB):
            return super().action_exchange_receive_process_chained()
        for record in self:
            record.with_delay(identity_key=identity_exact).x12_receive_process_job()
        return None

    def x12_send_job(self) -> str:
        """Job: upload the file, retrying while the server cannot be reached."""
        self.ensure_one()
        if blockers := self._x12_send_blockers():
            raise RetryableJobError(
                self.env._(
                    "Waiting for %(names)s to be sent first.",
                    names=", ".join(blockers.mapped("identifier")),
                ),
                seconds=BLOCKED_RETRY_SECONDS,
            )
        # The job runs as whoever queued it, who may lack access to the storage
        # credentials the upload needs.
        record = self.sudo().with_context(**{IN_JOB: True})
        return record.action_exchange_send() or ""

    def x12_receive_process_job(self) -> None:
        """Job: receive one inbound file and process it."""
        self.ensure_one()
        record = self.with_context(**{IN_JOB: True})
        record.action_exchange_receive_process_chained()

    def _x12_send_job_pending(self) -> bool:
        """Whether the upload of this record is still waiting in the queue."""
        self.ensure_one()
        return bool(
            self.env["queue.job"]
            .sudo()
            .search_count(
                [
                    ("func_string", "=", f"{self!r}.{SEND_JOB}()"),
                    ("state", "in", JOB_WAITING_STATES),
                ]
            )
        )

    def _x12_send_blockers(self) -> "EDIExchangeRecord":
        """Records that must be uploaded before this one. None by default."""
        return self.browse()

    def action_x12_resend(self) -> None:
        """Generate the file if it is missing, then queue it for sending."""
        for record in self:
            if record.edi_exchange_state == "output_error_on_send":
                record.action_retry()
            if not record.exchange_file:
                record.x12_generate_send()
            elif record.edi_exchange_state == "output_pending":
                record.action_exchange_send()

    def x12_acknowledge(self) -> EDIExchangeRecord | None:
        """Create, generate and send the acknowledgment of this inbound record.

        Meant for the done and error events of the record, which fire after its
        own processing is saved. A failure here is kept on the acknowledgment
        record and the original's chatter, so it never undoes that processing.
        """
        self.ensure_one()
        if self.direction != "input" or not self.type_id.ack_type_id:
            return None
        if not self.exchange_file or self.ack_exchange_id:
            return None
        if self._x12_is_acknowledgment():
            return None
        ack = self.exchange_create_ack_record()
        ack.x12_generate_send(
            on_error=lambda message: self._notify_related_record(message, "error")
        )
        return ack

    def _x12_is_acknowledgment(self) -> bool:
        """Whether the file is a functional acknowledgment (never acknowledged)."""
        try:
            sets = document_sets(self._get_file_content())
        except ValueError:
            return False
        return any(group == FUNCTIONAL_ACKNOWLEDGMENT for group, _set in sets)

    def x12_generate_send(self, on_error: Callable[[str], None] | None = None) -> bool:
        """Generate this output record and queue its upload, without ever raising.

        A failure (a value the partner requires is missing, say) stays on the
        record, which can be generated again once it is fixed, and is passed to
        ``on_error`` so the person who caused it sees it. The upload is a job,
        so a success here means "queued": see ``action_exchange_send``.

        The file is generated as a system task: whoever validated the delivery
        or pressed the button may lack access to the accounting records the
        message needs. Database errors are not ours to swallow: they leave the
        transaction unusable and must reach the framework.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                # Not inside a job, whatever the caller is doing: the upload
                # and the 997 of an inbound file are jobs of their own.
                record = self.sudo().with_context(**{IN_JOB: False})
                record.action_exchange_generate()
                if record.edi_exchange_state == "output_pending":
                    record.action_exchange_send()
        except (OperationalError, IntegrityError):
            raise
        except Exception as error:
            _logger.exception("Exchange record %s could not be sent", self.id)
            message = str(error) or type(error).__name__
            self.write({"exchange_error": message})
            if on_error is not None:
                on_error(
                    self.env._(
                        "%(type)s could not be sent: %(error)s",
                        type=self.type_id.name,
                        error=message,
                    )
                )
            return False
        return True
