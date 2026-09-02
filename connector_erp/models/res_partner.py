from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    erp_external_id = fields.Char(string="External ERP ID", copy=False)
