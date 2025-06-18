import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_deposit_line = fields.Boolean(default=False)
