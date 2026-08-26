from odoo import fields, models


class WorkCenter(models.Model):
    _inherit = "mrp.workcenter"

    default_printer_id = fields.Many2one("print.printer")
