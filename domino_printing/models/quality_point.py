from odoo import api, fields, models
from odoo.exceptions import ValidationError


class QualityControlPoint(models.Model):
    _inherit = "quality.point"

    test_report_type = fields.Selection(
        selection_add=[("domino", "Domino")], ondelete={"domino": "set default"}
    )
    print_code = fields.Boolean()
    print_case = fields.Boolean()
    coding_domino_template = fields.Many2one("domino.print.template")
    case_domino_template = fields.Many2one("domino.print.template")

    @api.constrains
    def _check_test_report_type(self):
        for record in self:
            if record.test_report_type == "domino" and not record.operation_id:
                raise ValidationError(
                    self.env._(
                        "To use domino report type, QC must be on Work Order operation"
                    )
                )
