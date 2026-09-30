from odoo import fields, models


class PrintingPrinter(models.Model):
    _inherit = "printing.printer"

    # Optional for the same reason as label_format: printing.printer is an
    # upstream table that may already hold rows, and a required field without a
    # default becomes a NOT NULL column. An undeclared printer matches nothing.
    label_format = fields.Selection(
        selection=[
            ("zpl", "ZPL"),
            ("pdf", "PDF"),
        ],
        help="Format this printer is able to render. A printer only ever takes "
        "one format, so a report is only ever sent to a printer declared for "
        "its own. Leave empty only for a printer that no report is ever sent "
        "to.",
    )
    label_size_id = fields.Many2one(
        "printing.label.size",
        help="Label size this printer is loaded with. A template written for "
        "one size is not printable on another, so labels are only offered for "
        "a printer carrying their own size. Leave empty only for a printer no "
        "label is ever sent to.",
    )

    def _supports_report(self, report):
        self.ensure_one()
        return (
            self.label_format == report.label_format
            and self.label_size_id == report.label_size_id
        )
