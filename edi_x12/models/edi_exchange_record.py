import logging
from collections.abc import Callable

from odoo import fields, models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord

from ..x12.reading import document_sets

_logger = logging.getLogger(__name__)


FUNCTIONAL_ACKNOWLEDGMENT = "FA"


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
        """Generate and send this output record without ever raising.

        A failure (a value the partner requires is missing, say) stays on the
        record, which can be generated again once it is fixed, and is passed to
        ``on_error`` so the person who caused it sees it.

        The file is generated and sent as a system task: whoever validated the
        delivery or pressed the button may lack access to the accounting records
        or the storage credentials the message needs.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.sudo().action_exchange_generate_send()
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
