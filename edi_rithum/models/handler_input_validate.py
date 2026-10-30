import re

from odoo import models

from odoo.addons.edi_core_oca.exceptions import EDIValidationError
from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_core_oca.utils import get_checksum

# Rithum names its files <number>.md5<hash>.<extension>
MD5_IN_NAME = re.compile(r"\.md5([0-9A-Fa-f]{32})(?:\.|$)")


class RithumHandlerInputValidate(models.AbstractModel):
    _name = "edi.rithum.handler.input.validate"
    _inherit = "edi.oca.handler.input.validate"
    _description = "Rithum file integrity check"

    def input_validate(self, exchange_record: EDIExchangeRecord, **kw) -> None:
        """Reject a file whose MD5 differs from the one in its name.

        Every file Rithum generates carries the MD5 of its exact content in the
        name, so a truncated or damaged download is caught before anything is
        read from it. A name without an MD5 is not checked.
        """
        match = MD5_IN_NAME.search(exchange_record.exchange_filename or "")
        if not match:
            return
        expected = match.group(1).lower()
        found = get_checksum(exchange_record._get_file_content(as_bytes=True))
        if found != expected:
            raise EDIValidationError(
                self.env._(
                    "The file does not match the MD5 in its name (expected "
                    "%(expected)s, found %(found)s): it was damaged in transfer.",
                    expected=expected,
                    found=found,
                )
            )
