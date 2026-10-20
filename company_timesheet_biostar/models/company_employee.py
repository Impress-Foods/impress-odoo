"""Employee-side linkage to BioStar.

Employees carry their BioStar numeric ``user_id`` in ``biostar_id``, entered
by HR instead of being auto-created from the server. The punch ingestion
contract of ``company_timesheet`` resolves punches through
``company.employee.source.ref`` rows (source ``biostar``, code = BioStar user
id), so this field keeps exactly one such reference in sync on every write:
creating/updating ``biostar_id`` upserts the reference, clearing it removes it
and assigning a code already used by another employee repoints that reference
rather than violating the unique constraint.
"""

from __future__ import annotations

from odoo import api, fields, models

from .biostar_mapper import SOURCE


class CompanyEmployee(models.Model):
    """Extensions of the employee directory for the BioStar connector."""

    _inherit = "company.employee"

    biostar_id = fields.Char(
        string="BioStar ID",
        copy=False,
        index=True,
        help="Numeric user id of this employee in BioStar 2; punches pulled "
        "from the BioStar backend are matched on it.",
    )
    biostar_ref_id = fields.Many2one(
        "company.employee.source.ref",
        string="BioStar Reference",
        compute="_compute_biostar_ref_id",
        store=True,
        compute_sudo=True,
        help="The single source reference derived from ``biostar_id``.",
    )

    _biostar_id_uniq = models.Constraint(
        "unique(biostar_id)",
        "This BioStar ID is already assigned to another employee.",
    )

    @api.depends("source_ref_ids.source", "source_ref_ids.code")
    def _compute_biostar_ref_id(self):
        for employee in self:
            employee.biostar_ref_id = employee.source_ref_ids.filtered(
                lambda ref: ref.source == SOURCE
            )[:1]

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_biostar_refs()
        return employees

    def write(self, vals):
        if "biostar_id" in vals:
            # The field's unique constraint fires inside super().write(); a
            # code moving between employees must release its previous holder
            # first, otherwise the mirror brings nothing and the write dies.
            self._release_conflicting_biostar_ids(vals["biostar_id"])
        result = super().write(vals)
        if "biostar_id" in vals:
            self._sync_biostar_refs()
        return result

    def _release_conflicting_biostar_ids(self, value):
        """Clear ``biostar_id`` on other employees claiming the same code."""
        if not isinstance(value, str) or not value.strip():
            return
        holder = self.search([("biostar_id", "=", value), ("id", "not in", self.ids)])
        if holder:
            holder.write({"biostar_id": False})

    def _sync_biostar_refs(self):
        """Mirror ``biostar_id`` into the ``biostar`` source reference."""
        Ref = self.env["company.employee.source.ref"]
        for employee in self:
            ref = employee.source_ref_ids.filtered(lambda item: item.source == SOURCE)[
                :1
            ]
            if not employee.biostar_id:
                if ref:
                    ref.unlink()
                continue
            if ref:
                ref.code = employee.biostar_id
            else:
                Ref.create(
                    {
                        "employee_id": employee.id,
                        "source": SOURCE,
                        "code": employee.biostar_id,
                    }
                )
