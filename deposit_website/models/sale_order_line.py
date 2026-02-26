import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _show_in_cart(self) -> bool:
        self.ensure_one()
        return super()._show_in_cart() and not self.is_deposit_line

    def get_deposit_container_qty(self) -> int:
        self.ensure_one()
        if self.order_id.website_id and self.product_id.requires_deposit:
            return int(self.product_uom_qty * self.product_id.qty_multiple)
        else:
            return super().get_deposit_container_qty()
