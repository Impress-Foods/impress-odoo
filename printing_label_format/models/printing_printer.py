from odoo import api, fields, models


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
    label_size = fields.Selection(
        selection=[
            ("2x4", "2x4"),
            ("3x3", "3x3"),
            ("4x6", "4x6"),
        ],
        help="Label size this printer is loaded with. A template written for "
        "one size is not printable on another, so labels are only offered for "
        "a printer carrying their own size. Leave empty only for a printer no "
        "label is ever sent to.",
    )

    @api.model
    def _label_format_map(self):
        """Map a report type onto the printer format that renders it.

        A transport that adds a report type adds the format it prints on here,
        so the pairing stays one predicate rather than a special case per
        transport.
        """
        return {"qweb-pdf": "pdf", "qweb-text": "zpl"}

    @api.model
    def _label_format_of(self, report):
        return self._label_format_map().get(report.report_type)

    @api.model
    def _label_size_of(self, report):
        """Return the label size ``report`` is written for.

        Unlike the format, this is not a function of the report type: the size
        lives in the template's own coordinates, so the report declares it.
        """
        return report.label_size

    def _supports_report(self, report):
        self.ensure_one()
        return self.label_format == self._label_format_of(report) and (
            self.label_size == self._label_size_of(report)
        )
