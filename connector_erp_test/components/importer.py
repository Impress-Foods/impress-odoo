from odoo.addons.component.core import Component


class TestPartnerImporter(Component):
    _name = "test.partner.importer"
    _inherit = ["erp.importer"]
    _apply_on = ["test.erp.partner"]
    _collection = "test.erp.backend"


class TestProductImporter(Component):
    _name = "test.product.importer"
    _inherit = ["erp.importer"]
    _apply_on = ["test.erp.product"]
    _collection = "test.erp.backend"
