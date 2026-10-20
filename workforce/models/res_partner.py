from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    workforce_employee_ids = fields.One2many(
        "workforce.employee",
        "partner_id",
        string="Employees",
        groups="base.group_user",
        help="Employee records whose underlying contact is this one.",
    )
    workforce_employee_count = fields.Integer(
        compute="_compute_workforce_employee_count",
        groups="base.group_user",
    )

    def _compute_workforce_employee_count(self):
        for partner in self:
            partner.workforce_employee_count = len(
                partner.sudo().workforce_employee_ids
            )

    def action_open_workforce_employee(self):
        self.ensure_one()
        employees = self.workforce_employee_ids
        if len(employees) > 1:
            return {
                "name": self.env._("Employees"),
                "type": "ir.actions.act_window",
                "res_model": "workforce.employee",
                "view_mode": "kanban,list,form",
                "domain": [("id", "in", employees.ids)],
            }
        return {
            "name": self.env._("Employee"),
            "type": "ir.actions.act_window",
            "res_model": "workforce.employee",
            "res_id": employees.id,
            "view_mode": "form",
        }


class ResUsers(models.Model):
    _inherit = "res.users"

    workforce_employee_count = fields.Integer(
        compute="_compute_workforce_employee_count",
        groups="base.group_user",
    )

    @api.depends("partner_id.workforce_employee_ids")
    def _compute_workforce_employee_count(self):
        for user in self:
            user.workforce_employee_count = len(
                user.partner_id.sudo().workforce_employee_ids
            )

    def action_open_workforce_employee(self):
        self.ensure_one()
        return self.partner_id.action_open_workforce_employee()
