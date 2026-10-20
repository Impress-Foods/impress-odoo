from odoo import api, fields, models


class ResUsers(models.Model):
    """Exposes the employee subtree of a user, used by timesheet record rules."""

    _inherit = "res.users"

    timesheet_employee_ids = fields.Many2many(
        "company.employee",
        "company_employee_timesheet_user_rel",
        "user_id",
        "employee_id",
        string="Timesheet Employees",
        compute="_compute_timesheet_employee_ids",
        compute_sudo=True,
    )

    @api.depends_context("uid")
    def _compute_timesheet_employee_ids(self):
        """Own employee plus everything below in the org chart.

        Two subtrees count, combined: the direct reporting chain
        (``child_of`` through the manager hierarchy) and the departments the
        employee manages, including their sub-departments. So a department
        head sees their team's timesheets even when team members never carry
        them as their direct ``parent_id``.
        """
        Employee = self.env["company.employee"].sudo()
        Department = self.env["company.department"].sudo()
        for user in self:
            employee = Employee.search(
                [("partner_id", "=", user.partner_id.id)], limit=1
            )
            if not employee:
                user.timesheet_employee_ids = False
                continue
            employees = Employee.search([("id", "child_of", employee.id)])
            managed_departments = Department.search([("manager_id", "=", employee.id)])
            if managed_departments:
                department_ids = Department.search(
                    [("id", "child_of", managed_departments.ids)]
                ).ids
                employees |= Employee.search([("department_id", "in", department_ids)])
            user.timesheet_employee_ids = employees
