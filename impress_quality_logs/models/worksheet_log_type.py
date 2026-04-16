from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class WorksheetLogType(models.Model):
    _name = "worksheet.log.type"
    _description = "Worksheet Log Type"
    _order = "sequence, name"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    active_template_id = fields.Many2one(
        "worksheet.template",
        string="Active Template",
        domain=Domain("res_model", "=", "quality.check"),
        tracking=True,
    )
    sequence = fields.Integer(default=10)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_linked_qp(self):
        for record in self:
            qp_count = self.env["quality.point"].search_count(
                Domain("log_type_id", "=", record.id)
            )
            if qp_count > 0:
                raise UserError(
                    self.env._(
                        'Cannot delete log type "%(name)s" - '
                        "%(count)s quality point(s) reference it",
                        name=record.name,
                        count=qp_count,
                    )
                )
