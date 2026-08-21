import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class IrReport(models.Model):
    _inherit = "ir.actions.report"

    print_report_id = fields.Many2one("print.report")
    report_type = fields.Selection(
        selection_add=[("api", "API")], ondelete={"api": "set default"}
    )

    @api.model
    def _render_api(self, report, res_ids, data=None):
        print_report = report.print_report_id
        if print_report.target_model_id.model != report.model:
            raise ValidationError(
                self.env._(
                    "Mismatch between print_report %(print)s and "
                    "ir.report %(report)s models",
                    print=print_report.target_model_id.name,
                    report=report.model,
                )
            )
        records = self.env[report.model].browse(res_ids)
        payload = print_report._render_json_payload(records, extra_data=data)
        return payload

    @api.model
    def print_api(self, report_ref, res_ids, data=None):
        report = self._get_report(report_ref)
        if not report:
            raise ValidationError(
                self.env._(
                    "Could not find report with report_ref %(ref)s", ref=report_ref
                )
            )
        if len(res_ids) > 1:
            raise ValidationError(
                self.env._("Cannot print API label for multiple records")
            )
        if len(res_ids) == 0:
            raise ValidationError(
                self.env._("Cannot print API label for empty recordset")
            )
        payload = self._render_api(report, res_ids, data)
        res = report.print_report_id.print_server_id._send(payload)
        return res
