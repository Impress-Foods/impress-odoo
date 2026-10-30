from odoo import models
from odoo.exceptions import UserError

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord


class EdiRithumIntake(models.AbstractModel):
    """What a retailer's module does with the files that come from it.

    A retailer's module inherits this model and lists in ROUTES the documents it
    reads: (functional group code, transaction set) -> the model that processes it.
    """

    _name = "edi.rithum.intake"
    _description = "Rithum partner intake"

    ROUTES: dict[tuple[str, str], str] = {}

    def process_document(
        self, exchange_record: EDIExchangeRecord, group: str, transaction_set: str
    ) -> None:
        """Hand the file to the model of the document it holds.

        A document the retailer's module does not read is an error that shows on
        the record, never a silent success.
        """
        model = self.ROUTES.get((group, transaction_set))
        if model is None:
            raise UserError(
                self.env._(
                    "The document %(set)s (group %(group)s) from %(partner)s is "
                    "not supported.",
                    set=transaction_set,
                    group=group,
                    partner=exchange_record.rithum_partner_id.name,
                )
            )
        self.env[model].process(exchange_record)
