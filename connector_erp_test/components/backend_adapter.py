from odoo.addons.component.core import Component
from odoo.addons.connector.exception import IDMissingInBackend

from .test_data import PARTNER_DATA, PRODUCT_DATA


class TestPartnerAdapter(Component):
    _name = "test.partner.adapter"
    _inherit = ["erp.backend.adapter"]
    _apply_on = ["test.erp.partner"]
    _collection = "test.erp.backend"

    def read_record(self, external_id, **kwargs):
        try:
            return dict(PARTNER_DATA[str(external_id)])
        except KeyError:
            raise IDMissingInBackend(external_id) from None


class TestProductAdapter(Component):
    _name = "test.product.adapter"
    _inherit = ["erp.backend.adapter"]
    _apply_on = ["test.erp.product"]
    _collection = "test.erp.backend"

    def read_record(self, external_id, **kwargs):
        try:
            return dict(PRODUCT_DATA[str(external_id)])
        except KeyError:
            raise IDMissingInBackend(external_id) from None
