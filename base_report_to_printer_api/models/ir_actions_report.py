from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("api", "API")],
        ondelete={"api": "set default"},
    )
    print_report_id = fields.Many2one(
        comodel_name="print.report",
        string="API Payload Profile",
        help="Structured field mappings used to build the API request.",
        ondelete="set null",
    )

    @api.onchange("report_type")
    def _onchange_report_type(self):
        for report in self:
            if report.report_type != "api":
                report.print_report_id = False

    @api.constrains("report_type", "print_report_id", "model")
    def _check_api_report_configuration(self):
        for report in self:
            print_report = report.print_report_id
            if report.report_type == "api":
                if not print_report:
                    raise ValidationError(
                        self.env._("An API report must have an API payload profile.")
                    )
                if print_report.target_model_id.model != report.model:
                    raise ValidationError(
                        self.env._(
                            "The API payload profile model must match the report model."
                        )
                    )
            elif print_report:
                raise ValidationError(
                    self.env._("Only API reports can have an API payload profile.")
                )

    @api.model
    def _render_api(self, report_ref, res_ids, data=None):
        raise UserError(
            self.env._(
                "API reports are rendered by the external API and cannot be "
                "rendered locally."
            )
        )

    def report_action(self, docids, data=None, config=True):
        if self.report_type == "api":
            config = False
        return super().report_action(docids, data=data, config=config)

    def print_document(self, record_ids, data=None):
        """Route API reports directly to their structured transport."""
        behavior = self.behaviour()
        printer = behavior.get("printer")

        if self.report_type == "api":
            if not printer or printer.backend != "api":
                raise UserError(self.env._("An API report must use an API printer."))
            behavior.pop("printer", None)
            return printer.print_api_document(
                self,
                record_ids,
                data=data,
                **behavior,
            )

        if printer and printer.backend == "api":
            raise UserError(
                self.env._("An API printer can only be used with a report of type API.")
            )
        return super().print_document(record_ids, data=data)

    def _get_printing_api_payload(
        self, record: models.Model, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return one flat Seagull-style payload for ``record``."""
        self.ensure_one()
        record.ensure_one()
        profile = self.print_report_id
        if not profile:
            return {}
        return profile._render_json_payload(
            record,
            extra_data=profile._get_record_data(data, record),
        )
