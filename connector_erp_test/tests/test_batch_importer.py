from odoo.addons.component.tests.common import TransactionComponentCase
from odoo.addons.integration_queue_job.tests.common import trap_jobs

from ..components.test_data import PARTNER_DATA


class TestErpBatchImporter(TransactionComponentCase):
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

    def test_batch_import_enqueues_one_job_per_record(self):
        with trap_jobs() as trap:
            imported = self.backend._run_batch_import("test.erp.partner")
            trap.assert_jobs_count(len(PARTNER_DATA))

        self.assertEqual(imported, len(PARTNER_DATA))

    def test_batch_import_performs_imports(self):
        with trap_jobs() as trap:
            self.backend._run_batch_import("test.erp.partner")
            trap.perform_enqueued_jobs()

        self.assertEqual(len(self._bindings()), len(PARTNER_DATA))

    def test_batch_import_skips_already_bound_records(self):
        self.PartnerBinding.import_record(self.backend, "1")

        with trap_jobs() as trap:
            imported = self.backend._run_batch_import("test.erp.partner")
            trap.assert_jobs_count(len(PARTNER_DATA) - 1)

        self.assertEqual(imported, len(PARTNER_DATA) - 1)

    def test_batch_import_force_reimports_everything(self):
        self.PartnerBinding.import_record(self.backend, "1")

        with trap_jobs() as trap:
            imported = self.backend._run_batch_import("test.erp.partner", force=True)
            trap.assert_jobs_count(len(PARTNER_DATA))

        self.assertEqual(imported, len(PARTNER_DATA))
