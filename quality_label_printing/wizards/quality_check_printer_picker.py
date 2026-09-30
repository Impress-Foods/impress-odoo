from odoo import api, fields, models
from odoo.exceptions import UserError


class QualityCheckPrinterPicker(models.TransientModel):
    _name = "quality.check.printer.picker"
    _description = "Pick a Printer and a Count for a Quality Check Label"

    quality_check_id = fields.Many2one(
        "quality.check", string="Quality Check", required=True, readonly=True
    )
    report_id = fields.Many2one(
        "ir.actions.report", string="Report", required=True, readonly=True
    )
    copies = fields.Integer(
        string="Labels",
        required=True,
        default=1,
        help="How many labels to print. Defaults to the quantity this run "
        "produces, which is what a work order step normally wants.",
    )
    report_label_format = fields.Char(compute="_compute_report_label_format")
    report_label_size_id = fields.Many2one(
        "printing.label.size", compute="_compute_report_label_format"
    )
    printer_id = fields.Many2one(
        "printing.printer",
        string="Printer",
        required=True,
        domain="[('label_format', '=', report_label_format),"
        " ('label_size_id', '=', report_label_size_id)]",
        help="Printer to print on. Starts on the one this step uses, and "
        "offers any other that can print this label.",
    )

    @api.depends("report_id.report_type", "report_id.label_size_id")
    def _compute_report_label_format(self) -> None:
        for picker in self:
            report = picker.report_id
            picker.report_label_format = report.label_format if report else False
            picker.report_label_size_id = report.label_size_id if report else False

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        check = self.env["quality.check"].browse(
            self.env.context.get("default_quality_check_id")
        )
        if not check.exists():
            raise UserError(self.env._("No quality check to print a label for."))
        report = check._get_label_report()
        printer = check.point_id.label_printer_id or report.behaviour().get("printer")
        if printer and (not printer.active or not printer._supports_report(report)):
            # A step or report naming the wrong, or an archived, machine should
            # be corrected rather than worked around at print time.
            printer = self.env["printing.printer"]
        values.update(
            {
                "quality_check_id": check.id,
                "report_id": report.id,
                "printer_id": printer.id,
                "copies": check._get_print_qty() or 1,
            }
        )
        return values

    def action_confirm(self):
        """Print the label, then move the check on.

        Printing happens before the step advances, so a printer that refuses the
        job leaves the check open to reprint rather than advancing a step whose
        label never came out.
        """
        self.ensure_one()
        check = self.quality_check_id
        target = check._get_label_target()
        self.report_id._print_label_for(
            target,
            self.printer_id,
            target_model=target._name,
            copies=self.copies,
            product_uom_qty=check.workorder_id.qty_producing
            or check.workorder_id.qty_production,
            product_uom_id=check.workorder_id.product_uom_id or check.product_id.uom_id,
        )
        check._next()
        return {"type": "ir.actions.act_window_close"}
