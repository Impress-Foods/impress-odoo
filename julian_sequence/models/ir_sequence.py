import logging
from datetime import datetime

from odoo import fields, models

_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _name = "ir.sequence"
    _inherit = "ir.sequence"

    implementation = fields.Selection(
        selection_add=[("julian", "Julian")],
        default="standard",
        ondelete={"julian": "set default"},
    )

    def _get_number_next_actual(self):
        for seq in self:
            if seq.implementation == "julian":
                pass
            else:
                return super()._get_number_next_actual()

    def _next_do(self):
        if self.implementation == "julian" and self.env.context.get(
            "julian_product_id"
        ):
            base_serial = datetime.now().strftime("%y%j")
            # Check if standard YYDDD serial exists:
            if not self.env["stock.lot"].search(
                [
                    ("name", "=", base_serial),
                    ("product_id", "=", self.env.context["julian_product_id"]),
                ],
                limit=1,
            ):
                return base_serial
            else:
                # If standard YYDDD serial exists for that product, append -N
                # where N is the next available number starting from 1.
                unique_serial = False
                appended_number = 1
                serial_to_try = base_serial + "-" + str(appended_number)
                while not unique_serial:
                    if self.env["stock.lot"].search(
                        [
                            ("name", "=", serial_to_try),
                            ("product_id", "=", self.env.context["julian_product_id"]),
                        ],
                        limit=1,
                    ):
                        appended_number += 1
                        serial_to_try = base_serial + "-" + str(appended_number)
                    else:
                        unique_serial = True
                return serial_to_try

        return super()._next_do()
