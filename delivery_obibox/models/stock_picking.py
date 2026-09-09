import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    obibox_tracking_numbers = fields.Char(copy=False)
    obibox_hand_to_hand = fields.Boolean(default=False)
