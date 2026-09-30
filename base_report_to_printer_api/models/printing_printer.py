from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PrintingPrinter(models.Model):
    _inherit = "printing.printer"

    backend = fields.Selection(
        selection_add=[("api", "API")],
        ondelete={"api": "cascade"},
    )
    api_server_id = fields.Many2one(
        comodel_name="printing.api.server",
        string="API Endpoint",
        ondelete="restrict",
    )

    @api.onchange("backend")
    def _onchange_backend(self):
        for printer in self:
            if printer.backend != "api":
                printer.api_server_id = False

    @api.constrains("backend", "api_server_id")
    def _check_api_server(self):
        for printer in self:
            if printer.backend == "api" and not printer.api_server_id:
                raise ValidationError(
                    self.env._("An API printer must have an API endpoint configured.")
                )
            if printer.backend != "api" and printer.api_server_id:
                raise ValidationError(
                    self.env._(
                        "An API endpoint can only be assigned to an API printer."
                    )
                )

    @staticmethod
    def _normalise_api_record_ids(
        record_ids: Any, report: models.Model | None = None
    ) -> list[Any]:
        if record_ids is None and report:
            record_ids = report.env.context.get("active_ids", [])
        if hasattr(record_ids, "ids"):
            record_ids = record_ids.ids
        if isinstance(record_ids, int):
            return [record_ids]
        return list(record_ids or [])

    def print_api_document(
        self,
        report: models.Model,
        record_ids: Any,
        data: dict[str, Any] | None = None,
        **print_options: Any,
    ) -> bool:
        """Send structured label data to the configured API endpoint.

        Seagull-style APIs render templates themselves, so API printers do
        not need the QWeb document produced by the normal printer backends.
        One request is sent per record to keep the flat payload contract
        unambiguous for label templates.
        """
        self.ensure_one()
        if not report or report.report_type != "api":
            raise UserError(
                self.env._("An API printer can only print reports of type API.")
            )
        if not self.api_server_id:
            raise UserError(self.env._("The API printer has no endpoint configured."))
        if not report.print_report_id:
            raise UserError(
                self.env._(
                    "Configure an API payload profile before printing this report."
                )
            )

        record_ids = self._normalise_api_record_ids(record_ids, report)
        if not record_ids:
            raise UserError(self.env._("Cannot send an API print job without records."))

        records = report.env[report.model].browse(record_ids).exists()
        if not records:
            raise UserError(self.env._("No printable records were found."))

        for record in records:
            payload = report._get_printing_api_payload(record, data=data)
            payload = dict(payload or {})
            payload["_template"] = report.print_report_id.template
            payload["_printer"] = self.system_name or self.name
            result = self.api_server_id._send(payload)
            if not result.get("success"):
                message = result.get("message") or self.env._(
                    "The printing API rejected the job."
                )
                raise UserError(
                    self.env._(
                        "Failed to send the print job to the API: %(message)s",
                        message=self._format_api_message(message),
                    )
                )
        return True

    @staticmethod
    def _format_api_message(message: Any) -> str:
        if isinstance(message, dict):
            for key in ("error", "message", "detail"):
                if key in message:
                    return str(message[key])
            return ", ".join(f"{key}: {value}" for key, value in message.items())
        if isinstance(message, list):
            return ", ".join(str(value) for value in message)
        return str(message)

    def print_document(
        self,
        report: models.Model,
        content: str | bytes,
        action=None,
        doc_format="qweb-pdf",
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> bool:
        if self.backend != "api":
            return super().print_document(
                report,
                content,
                action=action,
                doc_format=doc_format,
                **kwargs,
            )

        self.ensure_one()
        if action is not None:
            kwargs.setdefault("action", action)
        return self.print_api_document(
            report,
            kwargs.pop("res_ids", None),
            data=data,
            **kwargs,
        )
