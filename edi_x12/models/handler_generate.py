from odoo import models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord

from ..x12.reading import isa_control_number


class X12HandlerGenerate(models.AbstractModel):
    _name = "edi.x12.handler.generate"
    _inherit = "edi.oca.handler.generate"
    _description = "EDI X12 Handler Generate"

    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """The file content, built by the mapping model named in the type's settings.

        The interchange control number is kept on the record: the partner's
        acknowledgment names the file it answers by that number.
        """
        exchange_type = exchange_record.type_id
        text = exchange_type.x12_mapping().generate(exchange_record)
        control = isa_control_number(text)
        exchange_record.x12_control_number = str(control)
        if file_name := exchange_type.x12_file_name(control):
            exchange_record.exchange_filename = file_name
        return text
