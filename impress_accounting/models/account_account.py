from odoo import models


class AccountAccount(models.Model):
    _inherit = "account.account"

    def _get_name_search_account_types(self, move_type):
        res = super()._get_name_search_account_types(move_type)
        direction = move_type.split("_")[0]
        if direction == "in":
            res.append("asset_current")
        return res
