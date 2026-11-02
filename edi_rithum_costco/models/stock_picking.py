from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_core_oca.models.edi_exchange_type import EDIExchangeType


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "edi.exchange.consumer.mixin"]

    costco_can_confirm = fields.Boolean(
        compute="_compute_costco_can_confirm",
        help="A finished delivery of a Costco order with something to confirm.",
    )

    @api.depends("state", "sale_id", "move_line_ids.quantity")
    def _compute_costco_can_confirm(self) -> None:
        exchange_type = self.env.ref(
            "edi_rithum_costco.costco_856_out", raise_if_not_found=False
        )
        for picking in self:
            picking.costco_can_confirm = bool(exchange_type) and (
                picking._costco_is_shipment(exchange_type, resend=True)
            )

    def _action_done(self) -> bool:
        """Extends stock.picking._action_done: confirm Costco shipments once done."""
        result = super()._action_done()
        self._costco_confirm_shipments()
        return result

    def _create_backorder(self, backorder_moves=None) -> "StockPicking":
        """Extends stock.picking._create_backorder: tell Costco what is backordered.

        Odoo creates the backorder while it validates the delivery, before the
        shipment confirmation of this delivery is sent, so Costco gets the
        backorder first.
        """
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        backorders._costco_send_backorder_notices()
        return backorders

    def _costco_send_backorder_notices(self) -> None:
        """Send the backorder 856 of each backorder of a Costco delivery."""
        exchange_type = self.env.ref("edi_rithum_costco.costco_backorder_out")
        for backorder in self.filtered(lambda p: p._costco_is_backorder()):
            backorder._costco_send_notice(exchange_type)

    def _costco_is_backorder(self) -> bool:
        """A delivery created to finish a Costco delivery, with Costco lines."""
        self.ensure_one()
        return bool(
            self.backorder_id
            and self.picking_type_code == "outgoing"
            and self.sale_id._costco_is_order()
            and self.move_ids.sale_line_id.filtered("costco_sku")
        )

    def _costco_send_notice(self, exchange_type: EDIExchangeType) -> EDIExchangeRecord:
        """Create an exchange record of this type for the delivery and send it.

        A failure never blocks the delivery: it stays on the exchange record
        and is posted here, and the record can be generated again once fixed.
        """
        self.ensure_one()
        record = self._edi_create_exchange_record(exchange_type)
        record.x12_generate_send(
            on_error=lambda message: self.message_post(body=html_escape(message))
        )
        return record

    def _costco_notification(self, title: str, message: str, failed: bool) -> dict:
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "danger" if failed else "success",
                "sticky": failed,
            },
        }

    def _costco_confirm_shipments(self) -> None:
        """Send the shipment confirmation of each finished Costco delivery."""
        exchange_type = self.env.ref("edi_rithum_costco.costco_856_out")
        for picking in self.filtered(lambda p: p._costco_is_shipment(exchange_type)):
            picking._costco_send_notice(exchange_type)

    def action_costco_resend_confirmation(self) -> dict:
        """Send the shipment confirmation again, even if one was already sent.

        A new record is created, with a new interchange control number, and the
        earlier ones stay as history. The same checks apply as for the first
        send, so an incomplete delivery shows what is missing.
        """
        self.ensure_one()
        exchange_type = self.env.ref("edi_rithum_costco.costco_856_out")
        if not self._costco_is_shipment(exchange_type, resend=True):
            raise UserError(
                self.env._("This delivery has no Costco shipment to confirm.")
            )
        record = self._costco_send_notice(exchange_type)
        return self._costco_notification(
            self.env._("Shipment confirmation"),
            record.exchange_error or self.env._("The shipment confirmation was sent."),
            failed=bool(record.exchange_error),
        )

    def _costco_is_shipment(
        self, exchange_type: EDIExchangeType, resend: bool = False
    ) -> bool:
        """A finished delivery of a Costco order with something to confirm.

        Unless ``resend`` is set, a delivery that already has a confirmation does
        not count.
        """
        self.ensure_one()
        order = self.sale_id
        if (
            self.state != "done"
            or self.picking_type_code != "outgoing"
            or not order._costco_is_order()
        ):
            return False
        shipped = self.move_line_ids.filtered(
            lambda line: line.quantity > 0 and line.move_id.sale_line_id.costco_sku
        )
        if not shipped:
            return False
        if resend:
            return True
        return not self.exchange_record_ids.filtered(
            lambda r: r.type_id == exchange_type
        )
