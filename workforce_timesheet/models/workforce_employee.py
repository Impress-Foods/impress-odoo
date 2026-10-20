from odoo import fields, models


class WorkforceEmployee(models.Model):
    """Timesheet-side extensions to the employee directory record."""

    _inherit = "workforce.employee"

    source_ref_ids = fields.One2many(
        "workforce.employee.source.ref",
        "worker_id",
        string="Source References",
    )

    def _recompute_timesheet_sessions(self):
        """Rebuild the punch-derived timesheet sessions for these employees.

        Convenience wrapper used by the punch create/write/unlink hooks.
        """
        return self.env["workforce.timesheet"]._recompute_sessions(self)
