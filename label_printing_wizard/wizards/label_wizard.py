import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LabelWizard(models.TransientModel):
    _name = "label_wizard"
    _description = _("Label Wizard")

    name = fields.Char(_("Name"))
    model = fields.Selection(
        [
            ("product", _("Product")),
            ("lot", _("Lot")),
        ],
        default="product",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        _("Product"),
    )
    product_template_id = fields.Many2one("product.template", _("Product Template"))
    uom_id = fields.Many2one("uom.uom", related="product_id.uom_id")
    lot_id = fields.Many2one("stock.lot", _("Lot"))

    picking_id = fields.Many2one("stock.picking")

    product_qty = fields.Float(string="Quantity")

    label_qty = fields.Integer(default=1, string="Number of Labels")

    label_report = fields.Many2one("ir.actions.report", compute="_compute_label_report")

    label_size = fields.Selection(
        [
            ("2x4", _("2x4")),
            ("4x6", _("4x6")),
        ],
        default="2x4",
        required=True,
    )

    product_domain = fields.Char(compute="_compute_product_domain")
    lot_domain = fields.Char(compute="_compute_lot_domain")

    @api.depends("model", "product_template_id", "picking_id")
    def _compute_product_domain(self):
        for record in self:
            domain = []
            if self.model == "lot":
                domain = [("tracking", "in", ["serial", "lot"])]

            if self.product_template_id:
                domain += [("product_tmpl_id", "=", self.product_template_id.id)]

            if self.picking_id:
                domain += [("id", "in", self.picking_id.product_id.ids)]

            record.product_domain = domain

    @api.depends("product_id", "picking_id")
    def _compute_lot_domain(self):
        for record in self:
            domain = []
            if record.product_id:
                domain += [("product_id", "=", record.product_id.id)]

            if record.picking_id:
                domain += [("id", "in", record.picking_id.lot_id.ids)]

            record.lot_domain = domain

    @api.depends("model")
    def _compute_label_report(self):
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
                                "stock.label_lot_template"
                            )
                        case "4x6":
                            record.label_report = self.env.ref(
                                "label_printing_wizard.report_label_lot_template_4x6"
                            )

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

        return report.report_action(res_id, data=data)
