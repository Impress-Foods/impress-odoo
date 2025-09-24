import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockQuantPackage(models.Model):
    _inherit = "stock.package"

    material_added = fields.Boolean(default=False)
