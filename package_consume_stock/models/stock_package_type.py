from odoo import api, fields, models


class PackageType(models.Model):
    _inherit = "stock.package.type"

    packaging_material_ids = fields.Many2many("stock.package.material")
    has_packaging_material = fields.Boolean(compute="_compute_has_packaging_material")

    @api.depends("packaging_material_ids")
    def _compute_has_packaging_material(self):
        for record in self:
            record.has_packaging_material = bool(record.packaging_material_ids)
