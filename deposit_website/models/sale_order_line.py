import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _show_in_cart(self):
        self.ensure_one()
        return super()._show_in_cart() and not self.is_deposit_line
