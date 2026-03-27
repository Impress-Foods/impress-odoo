from odoo import fields, models


class QualityPointNA(models.Model):
    _inherit = ["quality.point"]

    allow_na = fields.Boolean(
        string="Allow Not Applicable",
        default=False,
        help="Quality checks for this point can be marked as Not Applicable",
    )
