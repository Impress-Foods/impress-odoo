from odoo import api, fields, models


class CompanyEmployeeSourceRef(models.Model):
    """Maps an external system's employee code to a ``company.employee``.

    A source module (``company_timesheet_{source}``) can use this to associate
    the codes it receives in a punch batch with an employee, independently for
    each source.
    """

    _name = "company.employee.source.ref"
    _description = "Employee Source Reference"
    _order = "source, code"

    employee_id = fields.Many2one(
        "company.employee",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        related="employee_id.company_id",
        store=True,
        index=True,
    )

    _source_code_uniq = models.Constraint(
        "unique(source, code)",
        "The code must be unique per source.",
    )

    @api.depends("source", "code")
    def _compute_display_name(self):
        for ref in self:
            if ref.source and ref.code:
                ref.display_name = f"{ref.source}: {ref.code}"
            else:
                ref.display_name = ref.code or ref.source or ""
