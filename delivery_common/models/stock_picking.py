import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shipping_label_attachment_id = fields.Many2one("ir.attachment")
