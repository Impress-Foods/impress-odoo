from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _check_build_page_info(self, i, p):
        page = super()._check_build_page_info(i, p)
        page["amount"] = page["amount"].replace("$", "").strip()
        return page
