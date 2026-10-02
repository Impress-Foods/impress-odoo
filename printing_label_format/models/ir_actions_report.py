from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    def _label_renderer_name(self) -> str | None:
        """Return this report type's render method, or ``None`` if a transport
        owns it and renders its own document.
        """
        renderers = {
            "qweb-pdf": "_render_qweb_pdf",
            "qweb-text": "_render_qweb_text",
        }
        return renderers.get(self.report_type)

    def _print_label_data(
        self,
        target: models.Model,
        copies: int,
        product_uom_qty: float = 0.0,
        product_uom_id: models.Model | None = None,
    ) -> dict[str, Any]:
        """Return the label payload for a single target.

        A dict keyed by the target id holding ``label_count``,
        ``product_uom_qty`` and ``product_uom_id``.

        This is the vocabulary every caller speaks.  A transport that names
        these differently translates them when it builds its own request rather
        than asking for a second spelling to be carried here.
        """
        self.ensure_one()
        target.ensure_one()
        target_data = {"label_count": copies}
        if product_uom_qty:
            target_data["product_uom_qty"] = product_uom_qty
            target_data["product_uom_id"] = (
                product_uom_id.id if product_uom_id else False
            )
        return {str(target.id): target_data}

    def _print_label_for(
        self,
        target: models.Model,
        printer: models.Model,
        target_model: str = "product.product",
        copies: int = 1,
        product_uom_qty: float = 0.0,
        product_uom_id: models.Model | None = None,
    ) -> None:
        """Validate and print one label for ``target`` on ``printer``.

        Every guard lives here so the printer can render the report and the
        print happen in one transaction.  A caller cannot reach the printer
        half-validated.

        A caller that draws ``target`` from a document of its own checks that
        the target belongs to it first; this knows nothing about where a target
        came from.
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
                data=data,
            )
        # A report takes its records from ``docids``, but some read ``active_ids``
        # from the context instead.  In a target="new" dialog that context is
        # the dialog's own, so the two disagree and the label renders from
        # whatever the context carried.  Pin both to the target.
        renderer = getattr(
            self.with_context(
                must_skip_send_to_printer=True,
                active_model=target._name,
                active_id=target.id,
                active_ids=target.ids,
            ),
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
