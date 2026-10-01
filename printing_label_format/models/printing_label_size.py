from odoo import fields, models


class PrintingLabelSize(models.Model):
    _name = "printing.label.size"
    _description = "Label Size"
    _order = "width_mm, height_mm"

    _name_uniq = models.Constraint(
        "unique(name)",
        "A label size with this name already exists.",
    )

    name = fields.Char(required=True, help="Name this label stock is known by.")
    width_mm = fields.Float(string="Width (mm)", required=True)
    height_mm = fields.Float(string="Height (mm)", required=True)
    active = fields.Boolean(default=True)
