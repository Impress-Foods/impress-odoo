import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    clickship_tracking_url = fields.Char()
    clickship_shipment_id = fields.Char()
