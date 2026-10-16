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
