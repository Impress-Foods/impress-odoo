from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWorkforceTimesheet(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Punch = cls.env["workforce.punch"]
        cls.Timesheet = cls.env["workforce.timesheet"]
        cls.employee = cls.env["workforce.employee"].create({"name": "Worker"})

    def _punch(self, direction, timestamp, external_id, employee=None):
        return self.Punch.create(
            {
                "worker_id": (employee or self.employee).id,
                "timestamp": timestamp,
                "direction": direction,
                "source": "test",
                "external_id": external_id,
            }
        )

    def _sessions(self, employee=None):
        return self.Timesheet.search(
            [("worker_id", "=", (employee or self.employee).id)]
        )

    def test_recompute_pairs_punches(self):
        self._punch("in", datetime(2026, 2, 2, 8, 0), "a1")
        self._punch("out", datetime(2026, 2, 2, 16, 30), "a2")
        session = self._sessions()
        self.assertEqual(len(session), 1)
        self.assertAlmostEqual(session.worked_hours, 8.5)
        self.assertEqual(session.date, datetime(2026, 2, 2).date())

    def test_recompute_on_punch_unlink(self):
        punch_in = self._punch("in", datetime(2026, 2, 3, 8, 0), "b1")
        self._punch("out", datetime(2026, 2, 3, 12, 0), "b2")
        self.assertEqual(len(self._sessions()), 1)
        punch_in.unlink()
        self.assertEqual(len(self._sessions()), 0)

    def test_orphan_out_makes_no_session(self):
        self._punch("out", datetime(2026, 2, 4, 12, 0), "c1")
        self.assertEqual(len(self._sessions()), 0)

    def test_punches_linked_to_session(self):
        punch_in = self._punch("in", datetime(2026, 2, 5, 8, 0), "d1")
        punch_out = self._punch("out", datetime(2026, 2, 5, 9, 0), "d2")
        self.assertTrue(punch_in.session_id)
        self.assertEqual(punch_in.session_id, punch_out.session_id)

    def test_single_open_session_constraint(self):
        self.Timesheet.sudo().create(
            {"worker_id": self.employee.id, "check_in": datetime(2026, 4, 1, 8, 0)}
        )
        with self.assertRaises(ValidationError):
            self.Timesheet.sudo().create(
                {
                    "worker_id": self.employee.id,
                    "check_in": datetime(2026, 4, 1, 9, 0),
                }
            )

    def _make_internal_user(self, login):
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )

    def test_record_rules_scope_own_and_downline(self):
        manager_user = self._make_internal_user("ts_manager")
        manager = self.env["workforce.employee"].create(
            {"name": "TS Manager", "partner_id": manager_user.partner_id.id}
        )
        report_user = self._make_internal_user("ts_report")
        report = self.env["workforce.employee"].create(
            {
                "name": "TS Report",
                "partner_id": report_user.partner_id.id,
                "parent_id": manager.id,
            }
        )
        other_user = self._make_internal_user("ts_other")
        other = self.env["workforce.employee"].create(
            {"name": "TS Other", "partner_id": other_user.partner_id.id}
        )
        for employee, tag in ((report, "rp"), (other, "ot")):
            self._punch("in", datetime(2026, 3, 1, 8, 0), f"{tag}1", employee)
            self._punch("out", datetime(2026, 3, 1, 9, 0), f"{tag}2", employee)

        # The report sees only their own session.
        report_sessions = self.Timesheet.with_user(report_user).search([])
        self.assertTrue(report_sessions)
        self.assertTrue(all(session.worker_id == report for session in report_sessions))

        # The manager sees their reports' sessions through the indirect downline.
        manager_sessions = self.Timesheet.with_user(manager_user).search([])
        self.assertIn(report, manager_sessions.worker_id)

        # An unrelated user sees their own, never the report's.
        other_sessions = self.Timesheet.with_user(other_user).search([])
        self.assertTrue(other_sessions)
        self.assertNotIn(report, other_sessions.worker_id)

    def test_record_rules_scope_department_manager_subtree(self):
        """A department head sees department members without direct parent."""
        head_user = self._make_internal_user("dept_head")
        head = self.env["workforce.employee"].create(
            {"name": "Dept Head", "partner_id": head_user.partner_id.id}
        )
        operations = self.env["workforce.department"].create(
            {"name": "Operations", "manager_id": head.id}
        )
        warehouse = self.env["workforce.department"].create(
            {"name": "Warehouse", "parent_id": operations.id}
        )
        member_user = self._make_internal_user("dept_member")
        member = self.env["workforce.employee"].create(
            {
                "name": "Team Member",
                "partner_id": member_user.partner_id.id,
                "department_id": operations.id,
            }
        )
        submember_user = self._make_internal_user("sub_member")
        submember = self.env["workforce.employee"].create(
            {
                "name": "Sub Member",
                "partner_id": submember_user.partner_id.id,
                "department_id": warehouse.id,
            }
        )
        for employee, tag in ((member, "dm"), (submember, "ds")):
            self._punch("in", datetime(2026, 3, 2, 8, 0), f"{tag}1", employee)
            self._punch("out", datetime(2026, 3, 2, 16, 0), f"{tag}2", employee)

        expected = {
            member.id,
            submember.id,
        }
        self.assertEqual(
            {e.id for e in head_user.timesheet_worker_ids if e != head},
            expected,
        )
        sessions = self.Timesheet.with_user(head_user).search([])
        self.assertEqual({s.worker_id.id for s in sessions} - {head.id}, expected)
