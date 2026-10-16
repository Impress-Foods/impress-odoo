from odoo import api, fields, models


class CompanyDepartment(models.Model):
    """Lightweight department used to group employees.

    Deliberately independent from ``hr.department`` so the employee directory
    can exist without relying on the core HR data model.
    """

    _name = "company.department"
    _description = "Department"
    _order = "complete_name"
    _parent_name = "parent_id"
    _parent_store = True

    name = fields.Char(string="Department Name", required=True, translate=True)
    complete_name = fields.Char(
        compute="_compute_complete_name",
        store=True,
        recursive=True,
    )
    parent_id = fields.Many2one(
        "company.department",
        string="Parent Department",
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "company.department",
        "parent_id",
        string="Child Departments",
    )
    manager_id = fields.Many2one("company.employee")
    employee_ids = fields.One2many(
        "company.employee",
        "department_id",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    note = fields.Text()

    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "The department name must be unique per company.",
    )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for department in self:
            if department.parent_id:
                department.complete_name = "%s / %s" % (
                    department.parent_id.complete_name,
                    department.name,
                )
            else:
                department.complete_name = department.name
