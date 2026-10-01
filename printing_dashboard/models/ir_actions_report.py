import logging
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
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

    def _get_dashboard_data_extra(self, copies: int) -> dict[str, Any]:
        """Return transport-specific keys to merge into the dashboard payload.

        The dashboard is transport-agnostic: a report whose transport reserves
        keys of its own overrides this instead of the dashboard special-casing
        its ``report_type``.  For example, the API transport's ``_qty`` key is
        the number of labels to print (``copies``).
        """
        return {}

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

    def _print_label_data(
        self,
        target: models.Model,
        copies: int,
        product_uom_qty: float = 0.0,
        product_uom_id: models.Model | None = None,
    ) -> dict[str, Any]:
        """Return the label payload for a single target.

        A dict keyed by the target id holding ``label_count``,
        ``product_uom_qty`` and ``product_uom_id``.  Keys supplied by
        ``_get_dashboard_data_extra`` are reserved for the transport.
        """
        self.ensure_one()
        target.ensure_one()
        target_data = {"label_count": copies}
        if product_uom_qty:
            target_data["product_uom_qty"] = product_uom_qty
            target_data["product_uom_id"] = (
                product_uom_id.id if product_uom_id else False
            )
        target_data.update(self._get_dashboard_data_extra(copies))
        return {str(target.id): target_data}

    def _print_label_for(
        self,
        target: models.Model,
        printer: models.Model,
        source: models.Model | None = None,
        target_model: str = "product.product",
        copies: int = 1,
        product_uom_qty: float = 0.0,
        product_uom_id: models.Model | None = None,
    ) -> None:
        """Validate and print one label for ``target`` on ``printer``.

        Every guard lives here so the target belongs to its source, the printer
        can render the report, and the print happen in one transaction.  A
        caller cannot reach the printer half-validated.
        """
        self.ensure_one()
        if not target:
            raise UserError(self.env._("Select a target before printing."))
        if copies < 1:
            raise ValidationError(self.env._("Copies must be greater than zero."))
        if self.model != target_model:
            raise UserError(
                self.env._("The selected report is not valid for the target.")
            )
        if source:
            source._check_target_allowed(target_model, target)
        if not printer:
            raise UserError(self.env._("Select a printer before printing."))
        if not printer._supports_report(self):
            raise UserError(
                self.env._(
                    "Printer %(printer)s cannot print %(report)s.",
                    printer=printer.display_name,
                    report=self.display_name,
                )
            )
        data = self._print_label_data(target, copies, product_uom_qty, product_uom_id)
        self._print_label(target, data=data, printer=printer)

    def _print_label(
        self,
        target: models.Model,
        data: dict[str, Any] | None = None,
        printer: models.Model | None = None,
    ) -> None:
        """Render ``target``'s label and send it to ``printer``.

        Renders and prints server-side: ``base_report_to_printer``'s client
        dispatchers resolve their own printer and would discard the one passed
        in.
        """
        self.ensure_one()
        printer = printer or self.browse()
        if not printer:
            raise UserError(self.env._("Select a printer before printing."))

        renderer_name = self._label_renderer_name()
        if renderer_name is None:
            return printer.print_document(
                self,
                None,
                doc_format=self.report_type,
                title=self.report_name,
                res_ids=target.ids,
            )
        renderer = getattr(
            self.with_context(must_skip_send_to_printer=True),
            renderer_name,
        )
        document, _doc_format = renderer(self.report_name, target.ids, data=data)
        printer.print_document(
            self,
            document,
            doc_format=self.report_type,
            title=self.report_name,
            res_ids=target.ids,
        )

    def _label_renderer_name(self) -> str | None:
        """Return this report type's render method, or ``None`` if a transport
        owns it and renders its own document.
        """
        renderers = {
            "qweb-pdf": "_render_qweb_pdf",
            "qweb-text": "_render_qweb_text",
        }
        return renderers.get(self.report_type)
