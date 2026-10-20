from datetime import datetime

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestTimesheetPortal(HttpCase):
    def test_portal_my_timesheets(self):
        employee = self.env["company.employee"].create(
            {"name": "Portal Worker", "email": "portal.worker@example.com"}
        )
        self.env["company.punch"].create(
            [
                {
                    "employee_id": employee.id,
                    "timestamp": datetime(2026, 5, 1, 8, 0),
                    "direction": "in",
                    "source": "test",
                    "external_id": "pp1",
                },
                {
                    "employee_id": employee.id,
                    "timestamp": datetime(2026, 5, 1, 16, 0),
                    "direction": "out",
                    "source": "test",
                    "external_id": "pp2",
                },
            ]
        )
        self.env["res.users"].create(
            {
                "name": "Portal Worker",
                "login": "portal.worker@example.com",
                "password": "portalworker",
                "partner_id": employee.partner_id.id,
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )

        self.authenticate("portal.worker@example.com", "portalworker")
        response = self.url_open("/my")
        self.assertEqual(response.status_code, 200)
        response = self.url_open("/my/timesheets")
        self.assertEqual(response.status_code, 200)
        self.assertIn("My Timesheets", response.text)
        # The employee column is rendered once per session row.
        self.assertIn("Portal Worker", response.text)

    def test_portal_manager_sees_downline_timesheets(self):
        """A portal user sees own sessions plus their manager subtree."""
        manager = self.env["company.employee"].create(
            {"name": "Portal Manager", "email": "portal.manager@example.com"}
        )
        worker = self.env["company.employee"].create(
            {
                "name": "Downline Worker",
                "email": "downline.worker@example.com",
                "parent_id": manager.id,
            }
        )
        self.env["company.punch"].create(
            [
                {
                    "employee_id": worker.id,
                    "timestamp": datetime(2026, 5, 4, 8, 0),
                    "direction": "in",
                    "source": "test",
                    "external_id": "md1",
                },
                {
                    "employee_id": worker.id,
                    "timestamp": datetime(2026, 5, 4, 16, 0),
                    "direction": "out",
                    "source": "test",
                    "external_id": "md2",
                },
            ]
        )
        self.env["res.users"].create(
            {
                "name": "Portal Manager",
                "login": "portal.manager@example.com",
                "password": "portalmanager",
                "partner_id": manager.partner_id.id,
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )

        self.authenticate("portal.manager@example.com", "portalmanager")
        response = self.url_open("/my/timesheets")
        self.assertEqual(response.status_code, 200)
        self.assertIn("My Timesheets", response.text)
        self.assertIn("Downline Worker", response.text)
