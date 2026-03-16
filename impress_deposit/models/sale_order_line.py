import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_deposit_line = fields.Boolean(default=False)

    def get_deposit_container_qty(self) -> int:
        self.ensure_one()
        if self.product_id.requires_deposit:
            return int(self.qty_delivered * self.product_id.qty_multiple)
        else:
            return 0
