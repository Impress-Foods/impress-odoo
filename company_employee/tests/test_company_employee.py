from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestCompanyEmployee(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env["company.employee"]
        cls.Department = cls.env["company.department"]

    def test_create_delegates_to_person_partner(self):
        employee = self.Employee.create({"name": "Jane Doe", "job_title": "Analyst"})
        self.assertEqual(employee.partner_id.company_type, "person")
        self.assertTrue(employee.employee_ref)
        self.assertEqual(employee.partner_id.name, "Jane Doe")
        # Writing a delegated field updates the underlying contact.
        employee.write({"work_email": "jane@example.com"})
        self.assertEqual(employee.partner_id.name, "Jane Doe")

    def test_employee_ref_is_unique_and_sequential(self):
        first = self.Employee.create({"name": "First"})
        second = self.Employee.create({"name": "Second"})
        self.assertNotEqual(first.employee_ref, second.employee_ref)

    def test_emergency_and_private_fields(self):
        employee = self.Employee.create(
            {
                "name": "John Smith",
                "private_phone": "+15145551234",
                "private_email": "john.private@example.com",
                "emergency_contact_name": "Mary Smith",
                "emergency_contact_relation": "Spouse",
                "emergency_contact_phone": "+15145559876",
            }
        )
        self.assertEqual(employee.emergency_contact_name, "Mary Smith")
        self.assertEqual(employee.emergency_contact_relation, "Spouse")
        self.assertEqual(employee.emergency_contact_phone, "+15145559876")
        self.assertEqual(employee.private_phone, "+15145551234")

    def test_department_and_manager_hierarchy(self):
        operations = self.Department.create({"name": "Operations"})
        logistics = self.Department.create(
            {
                "name": "Logistics",
                "parent_id": operations.id,
            }
        )
        self.assertEqual(logistics.complete_name, "Operations / Logistics")

        manager = self.Employee.create({"name": "Manager"})
        report = self.Employee.create(
            {
                "name": "Report",
                "parent_id": manager.id,
                "department_id": logistics.id,
            }
        )
        self.assertIn(report, manager.child_ids)
        self.assertEqual(report.department_id, logistics)
        self.assertIn(report, logistics.employee_ids)
        operations.manager_id = manager
        self.assertEqual(operations.manager_id, manager)

    def test_department_recursion_guard(self):
        department = self.Department.create({"name": "Root"})
        with self.assertRaises(UserError):
            department.parent_id = department.id

    def test_create_does_not_create_hr_employee(self):
        before = self.env["hr.employee"].search_count([])
        self.Employee.create(
            {
                "name": "No Hr Mirror",
                "email": "mirror@example.com",
            }
        )
        self.assertEqual(self.env["hr.employee"].search_count([]), before)

    def test_access_rights(self):
        employee = self.Employee.create({"name": "Target Employee"})
        basic_user = self.env["res.users"].create(
            {
                "name": "Basic User",
                "login": "basic_employee_user",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        # Internal users can read.
        employee.with_user(basic_user).read(["name"])
        # But cannot modify employee records.
        with self.assertRaises(AccessError):
            employee.with_user(basic_user).write({"job_title": "Hacker"})

    def test_portal_invite_grants_share_user(self):
        employee = self.Employee.create(
            {
                "name": "Portal Person",
                "email": "portal.person@example.com",
            }
        )
        patch_target = (
            "odoo.addons.portal.wizard.portal_wizard.PortalWizardUser._send_email"
        )
        with patch(patch_target, return_value=True):
            employee.action_invite_portal_user()

        employee.invalidate_recordset()
        self.assertTrue(employee.user_id)
        self.assertTrue(employee.user_id.share)
        self.assertTrue(employee.user_id._is_portal())
        self.assertEqual(len(employee.partner_id.user_ids), 1)

        # A second invitation must not create a duplicate user.
        with patch(patch_target, return_value=True):
            employee.action_invite_portal_user()
        employee.invalidate_recordset()
        self.assertEqual(len(employee.partner_id.user_ids), 1)

    def test_portal_invite_requires_email(self):
        employee = self.Employee.create({"name": "No Email"})
        with self.assertRaises(UserError):
            employee.action_invite_portal_user()

    def test_portal_invite_rejects_internal_user(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Internal Person",
                "email": "internal.person@example.com",
            }
        )
        self.env["res.users"].create(
            {
                "name": "Internal Person",
                "login": "internal_person",
                "partner_id": partner.id,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        employee = self.Employee.create(
            {
                "name": "Internal Person",
                "partner_id": partner.id,
            }
        )
        with self.assertRaises(UserError):
            employee.action_invite_portal_user()

    def test_action_view_portal_user(self):
        employee = self.Employee.create(
            {
                "name": "Portal Person",
                "email": "portal.view@example.com",
            }
        )
        patch_target = (
            "odoo.addons.portal.wizard.portal_wizard.PortalWizardUser._send_email"
        )
        with patch(patch_target, return_value=True):
            employee.action_invite_portal_user()
        employee.invalidate_recordset()
        action = employee.action_view_portal_user()
        self.assertEqual(action["res_model"], "res.users")
        self.assertEqual(action["res_id"], employee.user_id.id)
