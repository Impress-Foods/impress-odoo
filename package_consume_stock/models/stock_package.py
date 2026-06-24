from odoo import fields, models


class StockQuantPackage(models.Model):
    _inherit = "stock.package"

    material_added = fields.Boolean(default=False)
