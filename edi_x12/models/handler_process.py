from odoo import models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord


class X12HandlerProcess(models.AbstractModel):
    _name = "edi.x12.handler.process"
    _inherit = "edi.oca.handler.process"
    _description = "EDI X12 Handler Process"

    def process(self, exchange_record: EDIExchangeRecord) -> None:
        """Hand the record to the mapping model named in the type's x12 settings."""
        exchange_record.type_id.x12_mapping().process(exchange_record)
