# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

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
        required=True,
    )

    product_id = fields.Many2one("product.product", _("Product"))
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_id")  
    lot_id = fields.Many2one("stock.lot", _("Lot"))

    product_qty = fields.Float()

    label_qty = fields.Integer()

    label_report = fields.Many2one("ir.actions.report", compute="_compute_label_report")

    @api.depends("model")
    def _compute_label_report(self):
        for record in self:
            if record.model == "lot":
                record.label_report = self.env.ref(
                    "stock.label_lot_template"
                )
            else:
                record.label_report = self.env["ir.actions.report"]

    def print_label(self):
        return self.label_report.with_context(label_product_qty=self.product_qty).report_action(
            self.lot_id.id
        )
