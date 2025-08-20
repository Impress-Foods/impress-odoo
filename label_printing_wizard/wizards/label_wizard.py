import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LabelWizard(models.TransientModel):
    _name = "label_wizard"
    _description = _("Label Wizard")

    name = fields.Char()
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
        compute="_compute_product_id",
        inverse="_inverse_product_id",
    )
    product_template_id = fields.Many2one("product.template")

    packaging_id = fields.Many2one("product.packaging")

    uom_id = fields.Many2one("uom.uom", related="product_id.uom_id")
    lot_id = fields.Many2one("stock.lot")

    picking_id = fields.Many2one("stock.picking")

    product_qty = fields.Float(string="Quantity")
    packaging_qty = fields.Float()

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

    def _inverse_product_id(self):
        pass

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
            if self.model == "lot":
                domain = [("tracking", "in", ["serial", "lot"])]

            if self.product_template_id:
                domain += [("product_tmpl_id", "=", self.product_template_id.id)]

            if self.picking_id:
                product_ids = [move.product_id.id for move in self.picking_id.move_ids]
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

    @api.depends("model")
    def _compute_label_report(self) -> None:
        for record in self:
            match record.model:
                case "product":
                    match record.label_size:
                        case "2x4":
                            record.label_report = self.env.ref(
                                "label_printing_wizard.report_label_product_product_zpl_2x4"
                            )
                        case "4x6":
                            record.label_report = self.env.ref(
                                "label_printing_wizard.report_label_product_product_zpl_4x6"
                            )

                case "lot":
                    match record.label_size:
                        case "2x4":
                            record.label_report = self.env.ref(
                                "label_printing_wizard.report_label_lot_zpl_2x4"
                            )
                        case "4x6":
                            record.label_report = self.env.ref(
                                "label_printing_wizard.report_label_lot_zpl_4x6"
                            )

    @api.onchange("picking_id", "product_id", "lot_id")
    def get_product_qty(self) -> None:
        for record in self:
            if len(record.picking_id) == 0 or len(record.product_id) == 0:
                return

            quantity = 0
            if record.product_id.tracking in ["lot", "serial"] and record.lot_id:
                stock_move_line = self.env["stock.move.line"].search(
                    [
                        ("picking_id", "=", record.picking_id.id),
                        ("lot_id", "=", record.lot_id.id),
                    ]
                )

                quantity = sum(stock_move_line.mapped("qty_done"))

            else:
                stock_move = self.env["stock.move"].search(
                    [
                        ("picking_id", "=", record.picking_id.id),
                        ("product_id", "=", record.product_id.id),
                    ]
                )
                quantity = sum(stock_move.mapped("product_uom_qty"))

            record.product_qty = quantity

    def create(self, vals_list):
        _logger.warning(self.env.context)
        return super().create(vals_list)

    def print_label(self):
        report = self.label_report
        res_id = 0

        data = None

        if len(report) == 0:
            raise UserError(_("Report type not supported"))

        match self.model:
            case "product":
                res_id = self.product_id.id

            case "lot":
                res_id = self.lot_id.id

        report = report.with_context(label_count=self.label_qty)
        if self.product_qty != 0:
            report = report.with_context(label_product_qty=self.product_qty)
        if self.packaging_id:
            report = report.with_context(label_packaging_id=self.packaging_id.id)

            if self.packaging_qty != 0:
                report = report.with_context(label_packaging_qty=self.packaging_qty)

        return report.report_action(res_id, data=data)
