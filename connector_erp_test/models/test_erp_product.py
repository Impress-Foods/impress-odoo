from odoo import fields, models


class TestErpProduct(models.Model):
    _name = "test.erp.product"
    _inherit = ["erp.product.binding"]
    _inherits = {"product.product": "odoo_id"}
    _description = "Test ERP Product Binding"

    odoo_id = fields.Many2one(
        "product.product", string="Product", required=True, ondelete="cascade"
    )
    backend_id = fields.Many2one("test.erp.backend", required=True, ondelete="cascade")

    _backend_external_uniq = models.Constraint(
        "UNIQUE(backend_id, external_id)",
        "A product can only be bound once per backend.",
    )
