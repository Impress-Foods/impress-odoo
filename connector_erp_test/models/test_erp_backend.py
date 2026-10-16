from odoo import models


class TestErpBackend(models.Model):
    _name = "test.erp.backend"
    _inherit = ["erp.backend"]
    _description = "Test ERP Backend"
