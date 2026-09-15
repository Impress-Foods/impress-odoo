from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class PrintWizard(models.TransientModel):
    _name = "print.wizard"
    _description = "Wizard for API printing"

    ir_actions_report_id = fields.Many2one(
        "ir.actions.report", required=True, ondelete="cascade"
    )
    print_report_id = fields.Many2one(
        "print.report", related="ir_actions_report_id.print_report_id"
    )

    printer_id = fields.Many2one("print.printer", required=True)
    available_printer_ids = fields.Many2many(
        "print.printer", compute="_compute_available_printer_ids"
    )
    qty = fields.Integer(default=1)
    preview_ids = fields.One2many("print.wizard.preview", "wizard_id")

    result_printer_id = fields.Many2one("print.printer", readonly=True)
    result_printer_name = fields.Char(readonly=True)
    result_qty = fields.Integer(readonly=True)
    result_ready = fields.Boolean(readonly=True)

    @api.depends("print_report_id")
    def _compute_available_printer_ids(self):
        printer_model = self.env["print.printer"]
        for wizard in self:
            wizard.available_printer_ids = printer_model.search(
                self._available_printer_domain(wizard.print_report_id)
            )

    @api.model
    def _available_printer_domain(self, print_report):
        domain = Domain("active", "=", True)
        if print_report.print_server_id:
            domain &= Domain("server_id", "=", print_report.print_server_id.id)
        return domain

    @api.model
    def open_wizard(self, report_id, active_ids, defaults=None):
        """Create a print wizard and return the action opening it.

        ``defaults`` may carry a preselected ``printer_id``, ``qty`` and a
        ``preview`` mapping rendered by the caller.
        """
        report = self.env["ir.actions.report"].browse(report_id)
        if report.report_type != "api" or not report.print_report_id:
            raise ValidationError(
                self.env._(
                    "%(report)s is not a valid API printing report.",
                    report=report.display_name,
                )
            )

        defaults = defaults or {}
        printer = self.env["print.printer"].browse(
            defaults.get("printer_id") or []
        ) or self.env["print.printer"].search(
            self._available_printer_domain(report.print_report_id), limit=1
        )
        if not printer:
            raise ValidationError(
                self.env._(
                    "No printer is available for %(report)s.",
                    report=report.name,
                )
            )

        wizard = self.create(
            {
                "ir_actions_report_id": report.id,
                "printer_id": printer.id,
                "qty": defaults.get("qty") or 1,
            }
        )

        preview = defaults.get("preview")
        if preview is None:
            preview = self._render_preview(report, active_ids)
        wizard._create_preview_lines(preview)

        action = self.env["ir.actions.act_window"]._for_xml_id(
            "printing_connector.action_print_wizard"
        )
        action["res_id"] = wizard.id
        return action

    @api.model
    def _render_preview(self, report, active_ids):
        """Render the mapped payload for the single active record, if any."""
        print_report = report.print_report_id
        if print_report.target_model_id.model != report.model or len(active_ids) != 1:
            return {}
        records = self.env[report.model].browse(active_ids)
        return print_report._render_json_payload(records)

    def _create_preview_lines(self, preview):
        self.ensure_one()
        if not preview:
            return
        self.preview_ids = [
            (0, 0, {"key": str(key), "value": str(value)})
            for key, value in preview.items()
        ]

    def action_confirm(self):
        """Store the selection so the caller can trigger the print."""
        self.ensure_one()
        self.write(
            {
                "result_printer_id": self.printer_id.id,
                "result_printer_name": self.printer_id.technical_name,
                "result_qty": self.qty,
                "result_ready": True,
            }
        )
        return {"type": "ir.actions.act_window_close"}


class PrintWizardPreview(models.TransientModel):
    _name = "print.wizard.preview"
    _description = "Print wizard label preview line"

    wizard_id = fields.Many2one("print.wizard", required=True, ondelete="cascade")
    key = fields.Char()
    value = fields.Char()
