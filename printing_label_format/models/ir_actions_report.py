from odoo import api, fields, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    # The report side of the pairing, so both halves are fields a domain can
    # compare. Plain text rather than a Selection: the value comes from
    # _label_format_map, which another module may extend with a format this
    # field has no choice for.
    label_format = fields.Char(
        compute="_compute_label_format",
        store=True,
        help="Format this report renders as, derived from its type.",
    )

    # Declared rather than derived: the size lives in the template's own
    # coordinates, so a report says what it is written for. It is the other
    # half of the pairing printing.printer declares, which is why it lives
    # here rather than with the dashboard that consumes it.
    label_size_id = fields.Many2one(
        "printing.label.size",
        help="Label size this report is written for. It only matters for a "
        "label report: a template written for one size is not printable on "
        "another, so a label is only offered for a printer carrying the same "
        "size.",
    )

    @api.model
    def _label_report_types(self) -> list:
        """Return the report types that produce a label.

        Not every report that carries a format is a label: a PDF the printer
        stack can render is a document.  A transport that ships labels adds its
        type here.
        """
        return ["qweb-text"]

    @api.model
    def _label_format_map(self):
        """Map a report type onto the printer format that renders it.

        A transport that adds a report type adds the format it prints on here,
        so the pairing stays one predicate rather than a special case per
        transport.
        """
        return {"qweb-pdf": "pdf", "qweb-text": "zpl"}

    @api.depends("report_type")
    def _compute_label_format(self):
        for report in self:
            report.label_format = self._label_format_map().get(report.report_type)
