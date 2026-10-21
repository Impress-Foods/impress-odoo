from odoo import fields, models


class TestErpPartner(models.Model):
    _name = "test.erp.partner"
    _inherit = ["erp.binding.mixin"]
    _inherits = {"res.partner": "odoo_id"}
    _description = "Test ERP Partner Binding"

    odoo_id = fields.Many2one(
        "res.partner", string="Partner", required=True, ondelete="cascade"
    )
    backend_id = fields.Many2one("test.erp.backend", required=True, ondelete="cascade")

    _backend_external_uniq = models.Constraint(
        "UNIQUE(backend_id, external_id)",
        "A partner can only be bound once per backend.",
    )
