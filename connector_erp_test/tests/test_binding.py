from psycopg2 import IntegrityError

from odoo.addons.component.tests.common import TransactionComponentCase
from odoo.addons.connector.exception import IDMissingInBackend

from ..components.test_data import PARTNER_DATA


class TestErpBackendMixin(TransactionComponentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["test.erp.backend"].create(
            {
                "name": "Test Backend",
                "base_url": "https://example.com",
                "api_key": "token",
            }
        )

    def test_backend_is_a_connector_collection(self):
        with self.backend.work_on("test.erp.partner") as work:
            self.assertEqual(work.collection, self.backend)


class TestErpPartnerBinding(TransactionComponentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["test.erp.backend"].create(
            {
                "name": "Test Backend",
                "base_url": "https://example.com",
                "api_key": "token",
            }
        )
        cls.PartnerBinding = cls.env["test.erp.partner"]

    def _bindings(self):
        return self.PartnerBinding.search([("backend_id", "=", self.backend.id)])

    def test_import_creates_binding_and_odoo_record(self):
        self.PartnerBinding.import_record(self.backend, "1")

        binding = self._bindings()
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding.external_id, "1")
        self.assertEqual(binding.name, PARTNER_DATA["1"]["name"])
        self.assertEqual(binding.name, binding.odoo_id.name)
        self.assertTrue(binding.sync_date)
        self.assertEqual(binding.state, "synced")

    def test_import_is_idempotent(self):
        self.PartnerBinding.import_record(self.backend, "1")
        self.PartnerBinding.import_record(self.backend, "1")
        self.assertEqual(len(self._bindings()), 1)

    def test_import_force_updates_existing_binding(self):
        self.PartnerBinding.import_record(self.backend, "1")
        binding = self._bindings()
        binding.name = "Locally changed"

        self.PartnerBinding.import_record(self.backend, "1", force=True)

        binding.invalidate_recordset()
        self.assertEqual(binding.name, PARTNER_DATA["1"]["name"])

    def test_unique_constraint(self):
        partner = self.env["res.partner"].create({"name": "Manual"})
        vals = {
            "odoo_id": partner.id,
            "backend_id": self.backend.id,
            "external_id": "1",
        }
        self.PartnerBinding.create(vals)

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.PartnerBinding.create(vals)

    def test_unknown_external_id_raises(self):
        with self.assertRaises(IDMissingInBackend):
            self.PartnerBinding.import_record(self.backend, "999")

    def test_binder_resolves_both_directions(self):
        self.PartnerBinding.import_record(self.backend, "1")
        binding = self._bindings()

        with self.backend.work_on("test.erp.partner") as work:
            binder = work.component(usage="binder")
            self.assertEqual(binder.to_internal("1"), binding)
            self.assertEqual(binder.to_external(binding), "1")
            self.assertEqual(binder.unwrap_binding(binding), binding.odoo_id)


class TestErpProductBinding(TransactionComponentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["test.erp.backend"].create(
            {
                "name": "Test Backend",
                "base_url": "https://example.com",
                "api_key": "token",
            }
        )
        cls.ProductBinding = cls.env["test.erp.product"]

    def test_import_creates_product_binding(self):
        self.ProductBinding.import_record(self.backend, "101")

        binding = self.ProductBinding.search([("backend_id", "=", self.backend.id)])
        self.assertEqual(len(binding), 1)
        self.assertEqual(binding.default_code, "WIDGET-1")
        self.assertEqual(binding.odoo_id.default_code, "WIDGET-1")
        self.assertEqual(binding._erp_product(), binding.odoo_id)
