from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    company_employee_ids = fields.One2many(
        "company.employee",
        "partner_id",
        string="Employees",
        groups="base.group_user",
        help="Employee records whose underlying contact is this one.",
    )
    company_employee_count = fields.Integer(
        compute="_compute_company_employee_count",
        groups="base.group_user",
    )

    def _compute_company_employee_count(self):
        for partner in self:
            partner.company_employee_count = len(partner.sudo().company_employee_ids)

    def action_open_company_employee(self):
        self.ensure_one()
        employees = self.company_employee_ids
        if len(employees) > 1:
            return {
                "name": self.env._("Employees"),
                "type": "ir.actions.act_window",
                "res_model": "company.employee",
                "view_mode": "kanban,list,form",
                "domain": [("id", "in", employees.ids)],
            }
        return {
            "name": self.env._("Employee"),
            "type": "ir.actions.act_window",
            "res_model": "company.employee",
            "res_id": employees.id,
            "view_mode": "form",
        }


class ResUsers(models.Model):
    _inherit = "res.users"

    company_employee_count = fields.Integer(
        compute="_compute_company_employee_count",
        groups="base.group_user",
    )

    @api.depends("partner_id.company_employee_ids")
    def _compute_company_employee_count(self):
        for user in self:
            user.company_employee_count = len(
                user.partner_id.sudo().company_employee_ids
            )

    def action_open_company_employee(self):
        self.ensure_one()
        return self.partner_id.action_open_company_employee()
