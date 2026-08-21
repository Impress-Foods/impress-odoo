from odoo import fields, models


class PrintPrinter(models.Model):
    _name = "print.printer"
    _description = "Printer for print API"

    active = fields.Boolean(default=True)

    name = fields.Char()
    technical_name = fields.Char()
