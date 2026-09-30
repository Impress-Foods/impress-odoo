from odoo import api, fields, models
from odoo.exceptions import ValidationError


class QualityPoint(models.Model):
    _inherit = "quality.point"

    # One report and one printer per step. Whoever configures the step knows
    # which label it prints and which machine that label is printed at, so
    # neither is a question the operator is asked on the floor.
    label_report_id = fields.Many2one(
        "ir.actions.report",
        string="Label Report",
        domain="[('model', 'in', ('product.product', 'stock.lot')),"
        " ('is_dashboard_report', '=', True)]",
        help="Label this step prints. Left empty, the printing dashboard "
        "picks a default for the product or the lot.",
    )
    label_printer_id = fields.Many2one(
        "printing.printer",
        string="Label Printer",
        help="Printer this workstation prints the label on. Left empty, the "
        "printer the report is already configured for is used. The operator "
        "can still print elsewhere when printing.",
    )

    @api.constrains("label_report_id", "label_printer_id")
    def _check_label_printer_supports_report(self):
        for point in self:
            report = point.label_report_id
            printer = point.label_printer_id
            if report and printer and not printer._supports_report(report):
                raise ValidationError(
                    self.env._(
                        "Printer %(printer)s cannot print the labels report "
                        "%(report)s produces.",
                        printer=printer.display_name,
                        report=report.display_name,
                    )
                )
