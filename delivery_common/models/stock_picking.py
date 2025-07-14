import logging

from odoo import fields, models

from odoo.addons.web.controllers.utils import clean_action  # noqa

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shipping_label_attachment_id = fields.Many2one("ir.attachment")

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
