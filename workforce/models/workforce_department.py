from odoo import api, fields, models


class WorkforceDepartment(models.Model):
    """Department used to group employees and scope manager visibility."""

    _name = "workforce.department"
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
        "workforce.department",
        string="Parent Department",
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "workforce.department",
        "parent_id",
        string="Child Departments",
    )
    manager_id = fields.Many2one("workforce.employee")
    worker_ids = fields.One2many(
        "workforce.employee",
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
