import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def _run_manufacture(self, procurements):
        _logger.warning(f" stock rule: {procurements}")
        return super()._run_manufacture(procurements)

    @api.model
    def _aggregate_manufacturing_orders(self, procurements):
        pass
