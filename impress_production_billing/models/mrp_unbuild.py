import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpUnbuild(models.Model):
    _inherit = "mrp.unbuild"

    def action_unbuild(self):
        res = super().action_unbuild()
        if self.mo_id and self.mo_id.billing_sale_order_line_id:
            self.mo_id.billing_sale_order_line_id.qty_delivered -= self.product_qty
        return res
