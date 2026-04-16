from odoo import fields, models


class WorksheetTemplate(models.Model):
    _inherit = "worksheet.template"

    effective_date = fields.Date()
    xray_indicator_size = fields.Selection([("small", "Small"), ("large", "Large")])
