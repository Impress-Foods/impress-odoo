import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _deposit_needed(self) -> bool:
        self.ensure_one()
        res = super()._deposit_needed()
        if self.website_id:
            res = True
        return res
