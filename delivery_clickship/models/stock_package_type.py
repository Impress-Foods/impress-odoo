import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockPackageType(models.Model):
    _inherit = "stock.package.type"

    package_carrier_type = fields.Selection(
        selection_add=[("clickship", "ClickShip")], ondelete={"clickship": "set null"}
    )
