import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _name = "mrp.production"
    _inherit = "mrp.production"

    def _prepare_stock_lot_values(self):
        self = self.with_context(julian_product_id=self.product_id.id)  # type: ignore
        res = super()._prepare_stock_lot_values()
        return res
