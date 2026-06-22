import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    requires_deposit = fields.Boolean(related="product_id.requires_deposit")
