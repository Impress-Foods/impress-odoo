from odoo.addons.component.core import Component

from .test_data import PARTNER_DATA, PRODUCT_DATA


class TestPartnerBatchImporter(Component):
    _name = "test.partner.batch.importer"
    _inherit = ["erp.batch.importer"]
    _apply_on = ["test.erp.partner"]
    _collection = "test.erp.backend"

    def _iter_external_ids(self, **kwargs):
        return sorted(PARTNER_DATA)


class TestProductBatchImporter(Component):
    _name = "test.product.batch.importer"
    _inherit = ["erp.batch.importer"]
    _apply_on = ["test.erp.product"]
    _collection = "test.erp.backend"

    def _iter_external_ids(self, **kwargs):
        return sorted(PRODUCT_DATA)
