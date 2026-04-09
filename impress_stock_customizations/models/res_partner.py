from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    minimum_shelf_life = fields.Integer()
