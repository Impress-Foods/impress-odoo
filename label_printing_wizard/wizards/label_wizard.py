import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LabelWizard(models.TransientModel):
    _name = "label_wizard"
    _description = "Label Wizard"

    model = fields.Selection(
        [
            ("product", "Product"),
            ("lot", "Lot"),
        ],
        default="product",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        store=True,
        readonly=False,
        compute="_compute_product_id",
    )
    product_template_id = fields.Many2one("product.template")

    uom_id = fields.Many2one("uom.uom", related="product_id.uom_id")
    lot_id = fields.Many2one("stock.lot")

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

    picking_id = fields.Many2one("stock.picking")

    product_uom_qty = fields.Float(string="Quantity")

    label_qty = fields.Integer(default=1, string="Number of Labels")

    label_report = fields.Many2one("ir.actions.report", compute="_compute_label_report")

    label_size = fields.Selection(
        [
            ("2x4", "2x4"),
            ("4x6", "4x6"),
        ],
        default="2x4",
        required=True,
    )

    product_domain = fields.Char(compute="_compute_product_domain")
    lot_domain = fields.Char(compute="_compute_lot_domain")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.ensure_one()
        self.product_uom_id = False

    @api.depends("product_template_id")
    def _compute_product_id(self):
        for record in self:
            if not record.product_template_id:
                record.product_id = False
            else:
                record.product_id = record.product_template_id.product_variant_id

    @api.depends("model", "product_template_id", "picking_id")
    def _compute_product_domain(self):
        for record in self:
            domain = []
            if record.model == "lot":
                domain = [("tracking", "in", ["serial", "lot"])]

            if record.product_template_id:
                domain += [("product_tmpl_id", "=", record.product_template_id.id)]

            if record.picking_id:
                product_ids = record.picking_id.move_ids.product_id.ids
                domain += [("id", "in", product_ids)]

            record.product_domain = domain

    @api.depends("product_id", "picking_id")
    def _compute_lot_domain(self):
        for record in self:
            domain = []
            if record.product_id:
                domain += [("product_id", "=", record.product_id.id)]

            if record.picking_id:
                domain += [("id", "in", record.picking_id.move_line_ids.lot_id.ids)]

            record.lot_domain = domain

    @api.depends("model", "label_size")
    def _compute_label_report(self) -> None:
        for record in self:
            report_ref = False
            if record.model == "product":
                if record.label_size == "2x4":
                    report_ref = (
                        "label_printing_wizard.report_label_product_product_zpl_2x4"
                    )
                else:
                    report_ref = (
                        "label_printing_wizard.report_label_product_product_zpl_4x6"
                    )
            elif record.model == "lot":
                if record.label_size == "2x4":
                    report_ref = "label_printing_wizard.report_label_lot_zpl_2x4"
                else:
                    report_ref = "label_printing_wizard.report_label_lot_zpl_4x6"

            record.label_report = self.env.ref(report_ref) if report_ref else False

    @api.depends("product_id")
    def _compute_available_uom_ids(self):
        for record in self:
            if not record.product_id:
                record.available_uom_ids = False
                continue
            product = record.product_id
            uoms = product.uom_id | product.product_uom_ids.uom_id
            uoms |= product.uom_ids
            record.available_uom_ids = uoms
            if not record.product_uom_id:
                record.product_uom_id = product.uom_id

    @api.onchange("picking_id", "product_id", "lot_id")
    def get_product_uom_qty(self) -> None:
        for record in self:
            if not record.picking_id or not record.product_id:
                continue

            quantity = 0
            selected_uom = False
            if record.product_id.tracking in ["lot", "serial"] and record.lot_id:
                move_lines = record.picking_id.move_line_ids.filtered(
                    lambda ml, record=record: (
                        ml.product_id == record.product_id
                        and ml.lot_id == record.lot_id
                    )
                )
                quantity = sum(move_lines.mapped("qty_done"))
                if move_lines:
                    selected_uom = move_lines[0].product_uom_id
            else:
                moves = record.picking_id.move_ids.filtered(
                    lambda m, record=record: m.product_id == record.product_id
                )
                quantity = sum(moves.mapped("product_uom_qty"))
                if moves:
                    selected_uom = moves[0].product_uom_id

            record.product_uom_qty = quantity
            if selected_uom and selected_uom in record.available_uom_ids:
                record.product_uom_id = selected_uom

    def _make_values(self) -> dict:
        self.ensure_one()
        res_id = 0
        match self.model:
            case "product":
                res_id = self.product_id.id
            case "lot":
                res_id = self.lot_id.id
            case _:
                raise ValidationError(self.env._("Invalid model for wizard!"))

        data = {
            "label_count": self.label_qty,
            "product_uom_qty": self.product_uom_qty,
            "product_uom_id": self.product_uom_id.id,
        }

        return {res_id: data}

    def print_label(self):
        self.ensure_one()

        report = self.label_report
        if not report:
            raise UserError(self.env._("Report type not supported"))
        data = self._make_values()

        return report.report_action(list(data.keys()), data)
