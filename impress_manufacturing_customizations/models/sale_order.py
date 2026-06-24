from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_cancel(self):
        res = super()._action_cancel()
        mos = self.mapped("mrp_production_ids").filtered(
            lambda mo: mo.state not in ("done", "cancel")
        )
        mos.action_cancel()
        return res
