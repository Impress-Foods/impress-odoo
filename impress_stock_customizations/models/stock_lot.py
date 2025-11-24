import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    life_remaining = fields.Integer(compute="_compute_life_remaining")

    @api.depends("expiration_date")
    def _compute_life_remaining(self):
        today = fields.Date.today()
        for record in self:
            if not record.use_expiration_date or not record.expiration_date:
                record.life_remaining = 0
            else:
                diff = record.expiration_date.date() - today
                record.life_remaining = max(diff.days, 0)
