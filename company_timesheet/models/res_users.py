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
        Employee = self.env["company.employee"].sudo()
        for user in self:
            employee = Employee.search(
                [("partner_id", "=", user.partner_id.id)], limit=1
            )
            if employee:
                user.timesheet_employee_ids = Employee.search(
                    [("id", "child_of", employee.id)]
                )
            else:
                user.timesheet_employee_ids = False
