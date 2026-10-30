"""The 997: the one we send for each file, and the ones the retailers send us."""

from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import simple_xml, tset_997
from odoo.addons.edi_x12.x12.engine import validate_document
from odoo.addons.edi_x12.x12.reading import isa_sender

from .rithum_partner import EdiRithumPartner

FUNCTIONAL_ID = "FA"
ACCEPTED_STATUSES = frozenset({tset_997.ACCEPTED, tset_997.ACCEPTED_WITH_ERRORS})
STATE_ACCEPTED = "output_sent_and_processed"
STATE_REJECTED = "output_sent_and_error"


class EdiRithumMapping997(models.AbstractModel):
    _name = "edi.rithum.mapping.997"
    _description = "Rithum 997 Acknowledgment"

    @api.model
    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """Our detail-level 997 for the inbound file this record answers."""
        parent = exchange_record.parent_id
        text = parent._get_file_content()
        # The maps of the partner that sent the file check it. For an unknown sender
        # the exchange type's own maps hold no such document, so it is rejected.
        partner = self._partner(parent, text)
        maps = partner.map_path() if partner else parent.type_id.x12_map_path()
        outcome = validate_document(text, maps)
        # The answer goes back to whoever sent the file, as the identity it was
        # addressed to.
        envelope = exchange_record.backend_id.x12_reply_envelope(text, FUNCTIONAL_ID)
        return tset_997.acknowledge(
            text, outcome, envelope, exchange_record.type_id.x12_map_path()
        )

    def _partner(self, parent: EDIExchangeRecord, text: str) -> EdiRithumPartner:
        """The partner that sent the file, found again from its envelope.

        A file that failed to process keeps no partner: the error undoes what its
        processing wrote, and its rejection still needs the partner's maps.
        """
        if parent.rithum_partner_id:
            return parent.rithum_partner_id
        __, sender_id = isa_sender(text)
        return self.env["edi.rithum.partner"].from_sender(parent.backend_id, sender_id)

    @api.model
    def process(self, exchange_record: EDIExchangeRecord) -> None:
        """Record what a retailer's 997 says about the files we sent.

        The 997 names the file it answers by the group control number (AK102),
        which is the interchange control number we stored when we generated it.
        """
        outcome = exchange_record.type_id.x12_validate(
            exchange_record._get_file_content(),
            exchange_record.rithum_partner_id.map_path(),
        )
        acks = tset_997.read_functional_acknowledgments(simple_xml.parse(outcome.xml))
        answered = [self._sent_file(exchange_record, ack) for ack in acks]
        if answered:
            first = answered[0]
            exchange_record.write(
                {"parent_id": first.id, "model": first.model, "res_id": first.res_id}
            )
        for sent, ack in zip(answered, acks, strict=True):
            self._apply(sent, ack)

    def _sent_file(self, exchange_record: EDIExchangeRecord, ack) -> EDIExchangeRecord:
        """The file we sent that this acknowledgment answers."""
        number = str(int(ack.group_control)) if ack.group_control.isdigit() else ""
        sent = self.env["edi.exchange.record"].search(
            [
                ("backend_id", "=", exchange_record.backend_id.id),
                ("type_id.direction", "=", "output"),
                ("x12_control_number", "=", number),
            ],
            limit=1,
        )
        if not sent:
            raise UserError(
                self.env._(
                    "No file we sent has the control number %(number)s.",
                    number=ack.group_control,
                )
            )
        return sent

    def _apply(self, sent, ack) -> None:
        if ack.status in ACCEPTED_STATUSES:
            sent.edi_exchange_state = STATE_ACCEPTED
            sent._notify_ack_received()
            return
        sent.edi_exchange_state = STATE_REJECTED
        sent._notify_ack_received_error()
        sent._notify_related_record(self._rejection(ack), level="error")

    def _rejection(self, ack) -> str:
        """The partner's reasons, in words, for the chatter."""
        lines = [self.env._("The partner rejected the file (status %s).", ack.status)]
        lines += [
            self.env._("Group reason code %(code)s.", code=code)
            for code in ack.reason_codes
        ]
        for transaction in ack.transactions:
            lines.append(
                self.env._(
                    "Transaction %(set)s %(number)s: %(status)s.",
                    set=transaction.tset,
                    number=transaction.control_number,
                    status=transaction.status,
                )
            )
            lines += [
                self.env._(
                    "Segment %(id)s, position %(position)s, error code %(code)s.",
                    id=error.segment_id,
                    position=error.position,
                    code=error.syntax_code,
                )
                for error in transaction.errors
            ]
            lines += [
                self.env._("Reason code %(code)s.", code=code)
                for code in transaction.reason_codes
            ]
        return " ".join(lines)
