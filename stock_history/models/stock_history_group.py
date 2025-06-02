import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockHistoryGroup(models.Model):
    _name = "stock.history.group"
    _description = "StockHistoryGroup"

    name = fields.Char()

    history_line_ids = fields.One2many("stock.history.line", "history_group_id")

    history_config_id = fields.Many2one("stock.history.config")

    date = fields.Date()
