from odoo import models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord


class X12HandlerCheck(models.AbstractModel):
    _name = "edi.x12.handler.check"
    _inherit = "edi.oca.handler.check"
    _description = "EDI X12 Handler Check"

    def check(self, exchange_record: EDIExchangeRecord) -> bool:
        """Extends edi.oca.handler.check.check: there is nothing to look up.

        The framework calls the check handler for every output record in
        ``output_sent_and_error``, the state a rejecting 997 puts a file in. The
        storage handler's checker looks for done and error folders, which the
        Rithum server does not have. The outcome is already known, so the
        record stays as it is and the cron has nothing to do for it.
        """
        return False
