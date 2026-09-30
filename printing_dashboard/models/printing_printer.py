from odoo import fields, models


class PrintingPrinter(models.Model):
    _inherit = "printing.printer"

    show_in_dashboard = fields.Boolean(default=False)
