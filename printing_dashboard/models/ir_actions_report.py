import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    is_dashboard_report = fields.Boolean(
        string="Dashboard Report",
        help="Offer this report in the printing dashboard.",
    )

    @api.model
    def _dashboard_report_domain(self, model: str) -> Domain:
        """Return the domain of reports the dashboard is able to drive.

        The label types come from the label format module, so a transport that
        adds a label type is offered without naming the dashboard.
        """
        return Domain(
            [
                ("model", "=", model),
                ("is_dashboard_report", "=", True),
                ("report_type", "in", self._label_report_types()),
            ]
        )

    @api.model
    def _printable_reports_domain(self, model: str, printer: models.Model) -> Domain:
        """Return the dashboard reports of ``model`` that ``printer`` can print.

        The format and size halves of the pairing, so a caller does not spell
        them out.  A printer with no format names nothing.
        """
        if not printer or not printer.label_format:
            return Domain.FALSE
        return self._dashboard_report_domain(model) & Domain(
            [
                ("label_format", "=", printer.label_format),
                ("label_size_id", "=", printer.label_size_id.id),
            ]
        )

    def _is_dashboard_compatible(self) -> bool:
        """Return whether the dashboard can build a usable payload for this report."""
        self.ensure_one()
        return self.is_dashboard_report

    @api.constrains("is_dashboard_report", "report_type")
    def _check_dashboard_report_is_a_label(self) -> None:
        """Keep documents out of a dashboard that only prints labels.

        The flag is a box anyone can tick, and a packing slip ticked into it
        would be offered as a label and rendered onto a label printer.
        """
        label_types = self._label_report_types()
        for report in self.filtered("is_dashboard_report"):
            if report.report_type not in label_types:
                raise ValidationError(
                    self.env._(
                        "%(report)s is a %(type)s document, not a label, so it "
                        "cannot be offered in the printing dashboard.",
                        report=report.display_name,
                        type=report.report_type,
                    )
                )

    @api.model
    def _get_default_dashboard_report(self, model: str) -> models.Model:
        """Return a sensible default dashboard report for ``model``, if any."""
        domain = self._dashboard_report_domain(model)
        for report_type in self._label_report_types():
            report = self.search(
                domain & Domain("report_type", "=", report_type), limit=1
            )
            if report:
                return report
        return self.browse()

    @api.model
    def _get_default_printer(self) -> models.Model:
        """Return the printer this report is configured to print on, if any.

        Reads ``base_report_to_printer``'s own resolution and ignores a printer
        that is archived or cannot render the report.  Best effort: a failure
        leaves the caller to pick one.
        """
        self.ensure_one()
        try:
            printer = self.behaviour().get("printer")
            if not printer or not printer.active or not printer._supports_report(self):
                return self.env["printing.printer"]
            return printer
        except Exception:
            _logger.warning(
                "Could not resolve a default printer for report %s; the operator "
                "will have to pick one.",
                self.display_name,
                exc_info=True,
            )
            return self.env["printing.printer"]
