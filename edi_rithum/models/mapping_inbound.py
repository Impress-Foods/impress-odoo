"""Every retailer's files arrive in one folder: find the retailer, then the document."""

from typing import Self

from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12.reading import document_sets, isa_sender

FUNCTIONAL_ACKNOWLEDGMENT = ("FA", "997")


class EdiRithumMappingInbound(models.AbstractModel):
    _name = "edi.rithum.mapping.inbound"
    _description = "Rithum inbound documents"

    @api.model
    def process(self, exchange_record: EDIExchangeRecord) -> None:
        """Find who sent the file, then hand it to the module that reads its document.

        The file name says nothing about the sender or the document, and the
        framework picks the exchange type from the name before the content is read,
        so the sorting happens here. A sender no partner has, or a document its
        module does not read, is an error that shows on the record, never a silent
        success.
        """
        text = exchange_record._get_file_content()
        partner = self._partner(exchange_record, text)
        group, transaction_set = self._document(text)
        exchange_record.write(
            {"rithum_partner_id": partner.id, "x12_document": transaction_set}
        )
        if (group, transaction_set) == FUNCTIONAL_ACKNOWLEDGMENT:
            self.env["edi.rithum.mapping.997"].process(exchange_record)
            return
        partner.intake().process_document(exchange_record, group, transaction_set)

    def _partner(self, exchange_record: EDIExchangeRecord, text: str) -> Self:
        __, sender_id = isa_sender(text)
        partner = self.env["edi.rithum.partner"].from_sender(
            exchange_record.backend_id, sender_id
        )
        if not partner:
            raise UserError(
                self.env._(
                    "No Rithum partner has the interchange ID %(id)s.", id=sender_id
                )
            )
        return partner

    def _document(self, text: str) -> tuple[str, str]:
        documents = set(document_sets(text))
        if len(documents) != 1:
            raise UserError(
                self.env._(
                    "Expected one kind of document in the file, found: %(found)s.",
                    found=", ".join(f"{g}/{s}" for g, s in sorted(documents))
                    or self.env._("none"),
                )
            )
        return documents.pop()
