from odoo import fields, models


class QualityControlPoint(models.Model):
    _inherit = "quality.point"

    is_ccp = fields.Boolean()
