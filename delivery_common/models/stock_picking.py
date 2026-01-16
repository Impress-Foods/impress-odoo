import logging

from odoo import api, fields, models

from odoo.addons.web.controllers.utils import clean_action  # noqa

from ..tools.tools import text_from_html

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    tracking_email_sent = fields.Boolean(copy=False)
    shipping_label_attachment_id = fields.Many2one("ir.attachment", copy=False)
    delivery_instructions = fields.Char(
        compute="_compute_delivery_instructions",
        store=True,
    )

    ready_to_ship = fields.Boolean(copy=False, compute="_compute_ready_to_ship")

    @api.depends("sale_id", "sale_id.note", "sale_id.delivery_message")
    def _compute_delivery_instructions(self) -> None:
        for picking in self:
            note = ""
            if picking.sale_id:
                if picking.sale_id.note:
                    text = text_from_html(picking.sale_id.note)
                    # prevent default T&C from showing up
                    if picking.env.company.terms_type and text.find("http"):
                        pass
                    elif text == picking.env.company.invoice_terms:
                        pass
                    else:
                        note = text
                elif picking.sale_id.delivery_message:
                    note = picking.sale_id.delivery_message
            picking.delivery_instructions = note

    @api.depends("move_line_ids", "move_line_ids.picked")
    def _compute_ready_to_ship(self):
        for record in self:
            record.ready_to_ship = all(record.move_line_ids.mapped("picked"))

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

    def _send_confirmation_email(self):
        res = super()._send_confirmation_email()
        for record in self:
            if (
                not record.tracking_email_sent
                and record.carrier_id
                and record.carrier_id.send_confirmation_email
                and record.carrier_id.confirmation_template_id
            ):
                subtype_id = self.env["ir.model.data"]._xmlid_to_res_id(
                    "mail.mt_comment"
                )
                record.tracking_email_sent = True
                delivery_template = record.carrier_id.confirmation_template_id
                record.with_context(force_send=True).message_post_with_source(
                    delivery_template,
                    email_layout_xmlid="mail.mail_notification_light",
                    subtype_id=subtype_id,
                )

        return res
