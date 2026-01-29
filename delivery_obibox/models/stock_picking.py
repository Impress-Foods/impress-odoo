import logging

from odoo import fields, models

from odoo.addons.stock.models.stock_package import StockPackage

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    obibox_tracking_numbers = fields.Char(copy=False)

    def _get_packages(self) -> StockPackage:
        self.ensure_one()
        packages = self.env["stock.package"].search([("picking_ids", "in", [self.id])])
        return packages
