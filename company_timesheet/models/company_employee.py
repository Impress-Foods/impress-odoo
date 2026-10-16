from odoo import fields, models


class CompanyEmployee(models.Model):
    """Timesheet-side extensions to the employee directory record."""

    _inherit = "company.employee"

    source_ref_ids = fields.One2many(
        "company.employee.source.ref",
        "employee_id",
        string="Source References",
    )

    def _recompute_timesheet_sessions(self):
        """Rebuild the punch-derived timesheet sessions for these employees.

        Convenience wrapper used by the punch create/write/unlink hooks.
        """
        return self.env["company.timesheet"]._recompute_sessions(self)
