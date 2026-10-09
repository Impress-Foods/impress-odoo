from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping


class TestPartnerImportMapper(Component):
    _name = "test.partner.import.mapper"
    _inherit = ["erp.import.mapper"]
    _apply_on = ["test.erp.partner"]
    _collection = "test.erp.backend"

    @mapping
    def name(self, record):
        return {"name": record["name"]}

    @mapping
    def email(self, record):
        return {"email": record.get("email")}


class TestProductImportMapper(Component):
    _name = "test.product.import.mapper"
    _inherit = ["erp.import.mapper"]
    _apply_on = ["test.erp.product"]
    _collection = "test.erp.backend"

    @mapping
    def name(self, record):
        return {"name": record["name"]}

    @mapping
    def default_code(self, record):
        return {"default_code": record.get("code")}
