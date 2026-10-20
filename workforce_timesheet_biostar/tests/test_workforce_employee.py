from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, mute_logger

from odoo.addons.workforce_timesheet_biostar.models.biostar_mapper import SOURCE


class TestEmployeeBiostarLink(TransactionCase):
    """``workforce.employee.biostar_id`` maintains its ``biostar`` reference.

    The field is the only linkage requirement: punch ingestion resolves
    punches through ``workforce.employee.source.ref``, so these tests pin the
    mirror behaviour (create / update / move / clear).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env["workforce.employee"]
        cls.Ref = cls.env["workforce.employee.source.ref"]

    def _refs(self, employee):
        return employee.source_ref_ids.filtered(lambda ref: ref.source == SOURCE)

    def test_biostar_id_creates_reference(self):
        employee = self.Employee.create({"name": "Linked", "biostar_id": "42"})
        (ref,) = self._refs(employee)
        self.assertEqual((ref.code, ref.source), ("42", SOURCE))

    def test_blank_biostar_id_creates_no_reference(self):
        employee = self.Employee.create({"name": "Unlinked"})
        self.assertFalse(self._refs(employee))

    def test_write_updates_reference_code(self):
        employee = self.Employee.create({"name": "Repointed", "biostar_id": "42"})
        (ref,) = self._refs(employee)
        employee.write({"biostar_id": "43"})
        self.assertEqual(ref.code, "43")
        self.assertFalse(
            self.Ref.search([("code", "=", "42"), ("source", "=", SOURCE)])
        )

    def test_clearing_unlinks_reference(self):
        employee = self.Employee.create({"name": "Cleared", "biostar_id": "42"})
        employee.write({"biostar_id": False})
        self.assertFalse(self._refs(employee))

    def test_code_moving_between_employees_repoints(self):
        first = self.Employee.create({"name": "First", "biostar_id": "42"})
        second = self.Employee.create({"name": "Second"})
        second.write({"biostar_id": "42"})
        # The reference moved; the employee is unique per code.
        self.assertEqual(self._refs(second).code, "42")
        self.assertFalse(self._refs(first))
        self.assertFalse(first.biostar_ref_id)
        self.assertEqual(second.biostar_ref_id.worker_id.id, second.id)

    def test_biostar_id_uniqueness_on_employees(self):
        self.Employee.create({"name": "Holder", "biostar_id": "42"})
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
        ):
            self.Employee.create({"name": "Duplicate", "biostar_id": "42"})
