from odoo import api, fields, models
from odoo.exceptions import UserError


class WorkforceEmployee(models.Model):
    """Employee directory record.

    The record delegates to ``res.partner`` through ``_inherits`` so that all
    contact, address and bank information lives on the partner while the
    employee-specific attributes (job, department, emergency contact, portal
    user) live here.
    """

    _name = "workforce.employee"
    _description = "Workforce Employee"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _inherits = {"res.partner": "partner_id"}
    _order = "name"
    _parent_name = "parent_id"
    _parent_store = True

    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        required=True,
        ondelete="cascade",
        index=True,
        help="Underlying contact holding address, phone and email information.",
    )
    worker_ref = fields.Char(
        string="Worker ID",
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("workforce.employee")
        or "",
    )
    job_title = fields.Char(tracking=True)
    department_id = fields.Many2one("workforce.department", tracking=True)
    parent_id = fields.Many2one(
        "workforce.employee",
        string="Manager",
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    child_ids = fields.One2many(
        "workforce.employee",
        "parent_id",
        string="Direct Reports",
        domain=[("active", "=", True)],
    )
    parent_path = fields.Char(index=True)

    work_email = fields.Char()
    work_phone = fields.Char()
    private_phone = fields.Char(groups="workforce.group_workforce_officer")
    private_email = fields.Char(groups="workforce.group_workforce_officer")
    birthday = fields.Date(groups="workforce.group_workforce_officer", tracking=True)

    emergency_contact_name = fields.Char(
        string="Emergency Contact",
        groups="workforce.group_workforce_officer",
        tracking=True,
    )
    emergency_contact_relation = fields.Char(
        string="Relationship", groups="workforce.group_workforce_officer"
    )
    emergency_contact_phone = fields.Char(
        string="Emergency Phone",
        groups="workforce.group_workforce_officer",
        tracking=True,
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
    login_ids = fields.One2many(
        related="partner_id.user_ids",
        readonly=False,
        string="Logins",
        help="User logins sharing the employee's contact. The timesheet "
        "record rules scope visibility with the same link (a user sees the "
        "employee whose contact is their Related Contact, plus that "
        "employee's manager downline).",
    )
    notes = fields.Html(string="Internal Notes")

    _employee_ref_uniq = models.Constraint(
        "unique(worker_ref)",
        "The Employee ID must be unique.",
    )

    @api.depends("partner_id", "partner_id.user_ids", "partner_id.user_ids.share")
    def _compute_user_id(self):
        for employee in self:
            # ``user_id`` mirrors the contact's portal login, if one exists.
            employee.user_id = employee.partner_id.user_ids.filtered("share")[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # ``company_id`` and ``company_type`` are delegated to res.partner.
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("company_type", "person")
        return super().create(vals_list)

    def action_invite_portal_user(self):
        """Grant portal access to the employee's contact through the portal wizard.

        Reuses :class:`portal.wizard` so the invitation email, signup token and
        portal group management stay consistent with the rest of Odoo. Only the
        ``base.group_portal`` group is granted.
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
