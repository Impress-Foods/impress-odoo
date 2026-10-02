from typing import Any

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from ..tools import get_action_context


class PrintingDashboard(models.TransientModel):
    _name = "printing.dashboard"
    _description = "Printing Dashboard"

    source_model = fields.Char(readonly=True)
    source_id = fields.Integer(readonly=True)
    source_name = fields.Char(compute="_compute_source_name")
    target_model = fields.Selection(
        [("product.product", "Product"), ("stock.lot", "Lot / Serial Number")],
        default="product.product",
        required=True,
        string="Label For",
    )
    product_id = fields.Many2one(
        "product.product",
        ondelete="cascade",
        domain="[('type', '=', 'consu')] + "
        "([('id', 'in', available_target_product_ids)] if restrict_targets else [])",
    )
    lot_id = fields.Many2one(
        "stock.lot",
        ondelete="cascade",
        domain="[('product_id', '=', product_id)] + "
        "([('id', 'in', available_target_lot_ids)] if restrict_targets else [])",
    )
    # A source that knows which of its own records a label may be printed for
    # narrows the pickers to them, so an invalid choice is never offered.
    restrict_targets = fields.Boolean(compute="_compute_available_target_ids")
    available_target_product_ids = fields.Many2many(
        "product.product", compute="_compute_available_target_ids"
    )
    available_target_lot_ids = fields.Many2many(
        "stock.lot", compute="_compute_available_target_ids"
    )
    report_id = fields.Many2one(
        "ir.actions.report",
        string="Report",
        domain="[('id', 'in', available_report_ids)]",
        help="Report action to execute. Only reports marked as dashboard "
        "reports are offered, because only those can consume the payload the "
        "dashboard builds. Choosing a printer narrows this to the labels that "
        "machine can print.",
    )
    available_report_ids = fields.Many2many(
        "ir.actions.report",
        string="Available Reports",
        compute="_compute_available_report_ids",
    )
    copies = fields.Integer(string="Labels", default=1)
    printer_has_report = fields.Boolean(compute="_compute_printer_has_report")
    printer_id = fields.Many2one(
        "printing.printer",
        domain=[("show_in_dashboard", "=", True)],
        help="Printer this label goes to. Pick the machine you are standing at "
        "and the labels narrow to what it prints. It starts on whatever "
        "printer the report is already configured for, which is usually what "
        "you want.",
    )
    product_uom_qty = fields.Float(string="Quantity")
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Packaging",
        domain="[('id', 'in', available_uom_ids)]",
    )
    available_uom_ids = fields.Many2many(
        "uom.uom",
        string="Available UOMs",
        compute="_compute_available_uom_ids",
    )

    def _printer_report_domain(self) -> Domain:
        """Return the domain of labels ``self.printer_id`` is able to print."""
        self.ensure_one()
        if not self.printer_id or not self.target_model:
            return Domain.FALSE
        return self.env["ir.actions.report"]._printable_reports_domain(
            self.target_model, self.printer_id
        )

    @api.depends("printer_id", "target_model")
    def _compute_available_report_ids(self) -> None:
        """Narrow the reports to what the chosen printer can print.

        With no printer chosen nothing past the target model is narrowed: the
        machine is the thing an operator knows, and picking one moves the report
        onto its label.
        """
        report_model = self.env["ir.actions.report"]
        for dashboard in self:
            if not dashboard.printer_id:
                dashboard.available_report_ids = report_model.search(
                    report_model._dashboard_report_domain(dashboard.target_model)
                )
            else:
                dashboard.available_report_ids = report_model.search(
                    dashboard._printer_report_domain()
                )

    @api.depends("printer_id", "target_model")
    def _compute_printer_has_report(self) -> None:
        for dashboard in self:
            # An empty report list reads as a broken screen, and a machine set
            # up for a size no label uses yet is an ordinary thing to meet.
            dashboard.printer_has_report = bool(
                dashboard.printer_id
                and self.env["ir.actions.report"].search(
                    dashboard._printer_report_domain(), limit=1
                )
            )

    def _get_source_record(self) -> models.Model:
        """Return the record this dashboard was opened from, if still there."""
        self.ensure_one()
        if not self.source_model or not self.source_id:
            return self.env["printing.dashboard.source"].browse()
        if self.source_model not in self.env:
            return self.env["printing.dashboard.source"].browse()
        source = self.env[self.source_model].browse(self.source_id).exists()
        if not hasattr(source, "_get_print_dashboard_target_ids"):
            return self.env["printing.dashboard.source"].browse()
        return source

    @api.depends("source_model", "source_id")
    def _compute_source_name(self) -> None:
        for dashboard in self:
            source = dashboard._get_source_record()
            dashboard.source_name = source.display_name if source else False

    @api.depends("source_model", "source_id")
    def _compute_available_target_ids(self) -> None:
        """Offer only the targets the source can be labelled for.

        ``_get_print_dashboard_target_ids`` is the same answer
        ``_check_target_allowed`` validates against.  An empty mapping means the
        source does not restrict anything and the pickers stay open; an empty
        list means it restricts and owns none of that kind.
        """
        for dashboard in self:
            source = dashboard._get_source_record()
            candidates = source._get_print_dashboard_target_ids() if source else {}
            dashboard.restrict_targets = bool(candidates)
            dashboard.available_target_product_ids = self.env["product.product"].browse(
                candidates.get("product.product", [])
            )
            dashboard.available_target_lot_ids = self.env["stock.lot"].browse(
                candidates.get("stock.lot", [])
            )

    @api.depends("product_id")
    def _compute_available_uom_ids(self) -> None:
        for dashboard in self:
            if not dashboard.product_id:
                dashboard.available_uom_ids = False
                continue
            product = dashboard.product_id
            uoms = product.uom_id | product.product_uom_ids.uom_id
            dashboard.available_uom_ids = uoms | product.uom_ids

    @property
    def target(self) -> models.Model:
        """The record the report will run on, for the selected model."""
        self.ensure_one()
        if self.target_model == "stock.lot":
            return self.lot_id
        return self.product_id

    @api.onchange("target_model", "product_id", "lot_id")
    def _onchange_target(self) -> None:
        """Re-read the quantity from a source that can derive one.

        A transfer knows what it received for each of its own lots and
        products, so retargeting has to bring the quantity and its unit of
        measure along rather than leaving the previous target's numbers.
        """
        for dashboard in self:
            source = dashboard._get_source_record()
            if not source or not hasattr(source, "_label_quantity_for"):
                continue
            quantity, uom = source._label_quantity_for(dashboard.target)
            if quantity:
                dashboard.product_uom_qty = quantity
            if uom:
                dashboard.product_uom_id = uom

    @api.onchange("printer_id")
    def _onchange_printer_id(self):
        for dashboard in self:
            if not dashboard.printer_id:
                continue
            report = dashboard.report_id
            if report and not dashboard.printer_id._supports_report(report):
                dashboard.report_id = False

    @api.onchange("report_id")
    def _onchange_report_id(self) -> None:
        for dashboard in self:
            # A printer is only valid for the format of the report it will
            # print, so changing the report drops a printer that no longer
            # fits rather than leaving a mismatched pair to fail at print.
            if dashboard.printer_id and not dashboard.printer_id._supports_report(
                dashboard.report_id
            ):
                dashboard.printer_id = False

    @api.onchange("target_model")
    def _onchange_target_model(self) -> None:
        for dashboard in self:
            # ``product_id`` is deliberately kept when switching to a lot: it
            # stops being the target and becomes the filter for the lot picker.
            if dashboard.target_model == "product.product":
                dashboard.lot_id = False
            # The available reports depend on the model, so reset to that
            # model's default report (or empty when it has none).
            dashboard.report_id = self.env[
                "ir.actions.report"
            ]._get_default_dashboard_report(dashboard.target_model)

    @api.onchange("product_id")
    def _onchange_product_id(self) -> None:
        # A product change invalidates the packaging chosen for the previous
        # one, so fall back to the new product's own unit of measure.
        for dashboard in self:
            dashboard.product_uom_id = (
                dashboard.product_id.uom_id if dashboard.product_id else False
            )

    @api.model
    def open_from_source(
        self, source: models.Model, values: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return the action opening a dashboard for ``source``.

        The defaults live in the action's context, so the transient is created
        by the client when the dialog opens rather than eagerly here.
        """
        source.ensure_one()
        context = source._get_print_dashboard_context()
        context.update(values or {})
        defaults = self._prepare_dashboard_values(context)
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "printing_dashboard.action_printing_dashboard"
        )
        action_context = get_action_context(action)
        action_context.update(
            {f"default_{name}": value for name, value in defaults.items()}
        )
        action_context.update(
            {
                "active_model": self._name,
            }
        )
        action["context"] = action_context
        return action

    @api.model
    def action_open_for_record(self, res_model: str, res_id: int) -> dict | bool:
        """Open the dashboard for an arbitrary record, if it is a source.

        Lets a global entry point offer a prefilled dashboard when the record
        on screen knows its own context, and fall back to a blank one when it
        does not, without the caller having to know which models are sources.
        """
        model = self.env.get(res_model)
        if not res_id or model is None:
            return False
        if not hasattr(model, "action_open_print_dashboard"):
            return False
        return model.browse(res_id).action_open_print_dashboard()

    @api.model
    def _prepare_dashboard_values(self, context: dict[str, Any]) -> dict[str, Any]:
        target_model, product_id, lot_id = self.env[
            "printing.dashboard.source"
        ]._resolve_target(context)

        report_id = context.get("report_id")
        if isinstance(report_id, models.BaseModel):
            report_id = report_id.id
        elif isinstance(report_id, str):
            report_id = self.env.ref(report_id).id
        if not report_id and target_model:
            report_id = (
                self.env["ir.actions.report"]
                ._get_default_dashboard_report(target_model)
                .id
            )

        product_uom_id = context.get("product_uom_id")
        if isinstance(product_uom_id, models.BaseModel):
            product_uom_id = product_uom_id.id
        elif isinstance(product_uom_id, str):
            product_uom_id = self.env.ref(product_uom_id).id
        if not product_uom_id and product_id:
            product_uom_id = self.env["product.product"].browse(product_id).uom_id.id

        # A source that knows the workstation's printer names it here.
        printer_id = context.get("printer_id")
        if isinstance(printer_id, models.BaseModel):
            printer_id = printer_id.id
        elif isinstance(printer_id, str):
            printer_id = self.env.ref(printer_id).id
        if not printer_id and report_id:
            printer_id = (
                self.env["ir.actions.report"]
                .browse(report_id)
                ._get_default_printer()
                .id
            )

        return {
            "source_model": context.get("source_model"),
            "source_id": context.get("source_id"),
            "target_model": target_model,
            "product_id": product_id,
            "lot_id": lot_id,
            "report_id": report_id or False,
            "printer_id": printer_id or False,
            "copies": context.get("copies", 1),
            "product_uom_qty": context.get("product_uom_qty") or 0.0,
            "product_uom_id": product_uom_id or False,
        }

    def action_print(self) -> dict[str, Any]:
        """Print the selected label, then close the dashboard."""
        self.ensure_one()
        if not self.report_id:
            raise UserError(self.env._("Select a report before printing."))
        if not self.report_id._is_dashboard_compatible():
            raise UserError(
                self.env._(
                    "The selected report is not available in the printing dashboard."
                )
            )
        source = self._get_source_record()
        if source:
            # The dispatch is shared with callers that have no document behind
            # the target, so whether a target belongs to the document it was
            # drawn from is the dashboard's own question.
            source._check_target_allowed(self.target_model, self.target)
        self.report_id._print_label_for(
            self.target,
            self.printer_id,
            target_model=self.target_model,
            copies=self.copies,
            product_uom_qty=self.product_uom_qty,
            product_uom_id=self.product_uom_id,
        )
        return {"type": "ir.actions.act_window_close"}
