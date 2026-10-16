from odoo import api, fields, models
from odoo.exceptions import UserError


class CompanyEmployee(models.Model):
    """Employee directory record.

    The record delegates to ``res.partner`` through ``_inherits`` so that all
    contact, address and bank information lives on the partner while the
    employee-specific attributes (job, department, emergency contact, portal
    user) live here. This keeps contact data normalized and reuses the whole
    contacts feature set without depending on the data structures of ``hr``.
    """

    _name = "company.employee"
    _description = "Company Employee"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _inherits = {"res.partner": "partner_id"}
    _order = "name"

    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        required=True,
        ondelete="cascade",
        index=True,
        help="Underlying contact holding address, phone and email information.",
    )
    employee_ref = fields.Char(
        string="Employee ID",
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("company.employee")
        or "",
    )
    job_title = fields.Char(tracking=True)
    department_id = fields.Many2one("company.department", tracking=True)
    parent_id = fields.Many2one(
        "company.employee",
        string="Manager",
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    child_ids = fields.One2many(
        "company.employee",
        "parent_id",
        string="Direct Reports",
        domain=[("active", "=", True)],
    )

    work_email = fields.Char()
    work_phone = fields.Char()
    private_phone = fields.Char(groups="hr.group_hr_user")
    private_email = fields.Char(groups="hr.group_hr_user")
    birthday = fields.Date(groups="hr.group_hr_user", tracking=True)

    emergency_contact_name = fields.Char(
        string="Emergency Contact", groups="hr.group_hr_user", tracking=True
    )
    emergency_contact_relation = fields.Char(
        string="Relationship", groups="hr.group_hr_user"
    )
    emergency_contact_phone = fields.Char(
        string="Emergency Phone", groups="hr.group_hr_user", tracking=True
    )

    user_id = fields.Many2one(
        "res.users",
        string="Portal User",
        compute="_compute_user_id",
        store=True,
        copy=False,
        domain=[("share", "=", True)],
        help="Portal (external) user linked to this employee, if any.",
    )
    notes = fields.Html(string="Internal Notes")

    _employee_ref_uniq = models.Constraint(
        "unique(employee_ref)",
        "The Employee ID must be unique.",
    )

    @api.depends("partner_id", "partner_id.user_ids", "partner_id.user_ids.share")
    def _compute_user_id(self):
        for employee in self:
            # Only external (portal) users are exposed; internal users are
            # intentionally ignored.
            employee.user_id = employee.partner_id.user_ids.filtered("share")[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ``company_id`` and ``company_type`` are delegated to res.partner,
            # so they are routed to the auto-created contact.
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("company_type", "person")
        return super().create(vals_list)

    def action_invite_portal_user(self):
        """Grant portal access to the employee's contact through the portal wizard.

        Reuses :class:`portal.wizard` so the invitation email, signup token and
        portal group management stay consistent with the rest of Odoo. Only the
        ``base.group_portal`` group is granted, so no billable internal user is
        ever created.
        """
        self.ensure_one()
        if not self.partner_id.email:
            raise UserError(
                self.env._(
                    'Please set an email address on the contact "%s" before granting '
                    "portal access.",
                    self.name,
                )
            )
        wizard = (
            self.env["portal.wizard"]
            .with_context(active_test=False)
            .create(
                {
                    "partner_ids": [(6, 0, self.partner_id.ids)],
                }
            )
        )
        wizard_user = wizard.user_ids
        if wizard_user.is_internal:
            raise UserError(
                self.env._(
                    'The contact "%s" is linked to an internal user; portal access '
                    "cannot be granted.",
                    self.name,
                )
            )
        if wizard_user.is_portal:
            wizard_user.action_invite_again()
        else:
            wizard_user.action_grant_access()
        return wizard._action_open_modal()

    def action_view_portal_user(self):
        """Open the linked portal user form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Portal User"),
            "res_model": "res.users",
            "res_id": self.user_id.id,
            "view_mode": "form",
            "target": "current",
        }
