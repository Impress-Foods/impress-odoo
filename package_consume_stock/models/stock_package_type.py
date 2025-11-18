import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PackageType(models.Model):
    _inherit = "stock.package.type"

    packaging_material_ids = fields.Many2many("stock.package.material")
    has_packaging_material = fields.Boolean(compute="_compute_has_packaging_material")

    @api.depends("packaging_material_ids")
    def _compute_has_packaging_material(self):
        for record in self:
            if len(record.packaging_material_ids) > 0:
                record.has_packaging_material = True
            else:
                record.has_packaging_material = False
