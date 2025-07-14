import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    check_digit = fields.Boolean()

    @api.model
    def _gs1_check_digit(self, code):
        code = [int(x) for x in code]

        odds = code[0::2]
        evens = code[1::2]

        sum_of_digits = 3 * sum(odds) + sum(evens)
        nearest_ten = (
            ((sum_of_digits // 10) + 1) * 10
            if sum_of_digits % 10 != 0
            else sum_of_digits
        )
        check_digit = nearest_ten - sum_of_digits
        return str(check_digit)

    def get_next_char(self, number_text):
        res = super().get_next_char(number_text)
        if self.check_digit and res.isnumeric():
            check_digit = self._gs1_check_digit(res)
            res += check_digit
        return res
