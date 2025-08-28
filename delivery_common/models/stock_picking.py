import logging

from odoo import api, fields, models

from odoo.addons.web.controllers.utils import clean_action  # noqa

from ..tools.tools import text_from_html

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shipping_label_attachment_id = fields.Many2one("ir.attachment")
    delivery_instructions = fields.Char(
        compute="_compute_delivery_instructions",
        store=True,
    )

    @api.depends("sale_id", "sale_id.note", "sale_id.delivery_message")
    def _compute_delivery_instructions(self) -> None:
        for picking in self:
            note = ""
            if picking.sale_id:
                if picking.sale_id.note:
                    note = text_from_html(picking.sale_id.note)
                elif picking.sale_id.delivery_message:
                    note = picking.sale_id.delivery_message
            picking.delivery_instructions = note

    def _get_autoprint_report_actions(self) -> list[dict]:
        report_actions: list[dict] = super()._get_autoprint_report_actions()
        pickings_print_delivery_label = self.filtered(
            lambda p: p.picking_type_id.auto_print_delivery_label
        )
        if pickings_print_delivery_label:
            action = self.env.ref(
                "delivery_common.report_shipping_label"
            ).report_action(pickings_print_delivery_label.ids, config=False)
            clean_action(action, self.env)
            report_actions.append(action)

        return report_actions
