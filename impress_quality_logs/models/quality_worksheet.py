from odoo import fields, models


class QualityWorksheet(models.Model):
    _inherit = "worksheet.template"

    xray_indicator_size = fields.Selection([("small", "Small"), ("large", "Large")])
