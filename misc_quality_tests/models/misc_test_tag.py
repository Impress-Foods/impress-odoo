from random import randint

from odoo import fields, models


class MiscTestTag(models.Model):
    _name = "misc.test.tag"
    _description = "Misc Test Tag"

    _sql_constraints = [
        ("tag_name_unique", "unique(name)", "The tag name must be unique."),
    ]

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char()
    color = fields.Integer("Color Index", default=_get_default_color)
