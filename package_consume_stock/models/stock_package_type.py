import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PackageType(models.Model):
    _inherit = "stock.package.type"

    packaging_material_id = fields.Many2one("product.product")
    source_location_id = fields.Many2one("stock.location")
