from typing import Self

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord

CANCELLATION_TYPE = "edi_rithum_costco.costco_cancel_out"


class EdiRithumCostcoCancellation(models.Model):
    """Units of a Costco order we will not ship, and the reason we tell Costco."""

    _name = "edi.rithum.costco.cancellation"
    _inherit = ["mail.thread", "edi.exchange.consumer.mixin"]
    _description = "Costco Cancellation"
    _order = "id desc"

    name = fields.Char(
        readonly=True,
        copy=False,
        default=lambda self: self.env._("New"),
        help="Identifies the message (BSN02) in Costco's system.",
    )
    order_id = fields.Many2one(
        "sale.order", string="Order", required=True, index=True, readonly=True
    )
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    reason_id = fields.Many2one(
        "edi.rithum.costco.code",
        string="Reason",
        required=True,
        domain=[("code_type", "=", "cancel_reason")],
        tracking=True,
    )
    note = fields.Char(help="Free text sent with the reason.", size=80)
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Cancelled")],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )
    line_ids = fields.One2many("edi.rithum.costco.cancellation.line", "cancellation_id")

    @api.model_create_multi
    def create(self, vals_list) -> Self:
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                vals["name"] = sequence.next_by_code(self._name) or self.env._("New")
        return super().create(vals_list)

    def action_confirm(self) -> None:
        """Take the units off the order, then tell Costco.

        The message is sent last and never undoes the reduction: a failure stays
        on this record and in its chatter, and "Send again" retries it.
        """
        for cancellation in self:
            cancellation._check_can_cancel()
            cancellation._reduce_order()
            cancellation.state = "done"
            cancellation.send()

    def send(self) -> EDIExchangeRecord:
        """Create a new exchange record for this cancellation and send it."""
        self.ensure_one()
        exchange_type = self.env.ref(CANCELLATION_TYPE)
        record = self._edi_create_exchange_record(exchange_type)
        record.x12_generate_send(
            on_error=lambda message: self.message_post(body=html_escape(message))
        )
        return record

    def _check_can_cancel(self) -> None:
        self.ensure_one()
        if self.state != "draft":
            raise UserError(self.env._("This cancellation was already made."))
        if not self.order_id._costco_is_order():
            raise UserError(self.env._("The order did not come from Costco."))
        lines = self.line_ids.filtered(lambda line: line.quantity)
        if not lines:
            raise UserError(self.env._("Enter the quantity to cancel on a line."))
        for line in lines:
            if line.quantity < 0 or line.quantity > line.open_quantity:
                raise UserError(
                    self.env._(
                        "%(product)s: cancel between 0 and the %(open)s still open.",
                        product=line.sale_line_id.display_name,
                        open=line.open_quantity,
                    )
                )

    def _reduce_order(self) -> None:
        """Take the cancelled units off the order.

        Cancelling everything of an order with nothing delivered cancels the order
        itself (sale.order._action_cancel, which sale_stock extends to cancel its
        deliveries), and keeps the ordered quantities for the record. Otherwise
        each line is lowered by its cancelled quantity, which sale_stock
        propagates to the delivery.
        """
        self.ensure_one()
        if self._cancels_everything():
            self.order_id._action_cancel()
            return
        for line in self.line_ids.filtered(lambda line: line.quantity):
            line.sale_line_id.product_uom_qty -= line.quantity

    def _cancels_everything(self) -> bool:
        """Whether this leaves nothing to deliver on an order with nothing delivered."""
        self.ensure_one()
        order = self.order_id
        if any(order.order_line.mapped("qty_delivered")):
            return False
        cancelled = {line.sale_line_id: line.quantity for line in self.line_ids}
        return all(
            cancelled.get(line, 0) >= line.product_uom_qty - line.qty_delivered
            for line in order._costco_open_lines()
        )


class EdiRithumCostcoCancellationLine(models.Model):
    _name = "edi.rithum.costco.cancellation.line"
    _description = "Costco Cancellation Line"

    cancellation_id = fields.Many2one(
        "edi.rithum.costco.cancellation", required=True, ondelete="cascade"
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Order line",
        required=True,
        domain="[('order_id', '=', parent.order_id), ('costco_sku', '!=', False)]",
    )
    product_id = fields.Many2one(related="sale_line_id.product_id")
    open_quantity = fields.Float(
        compute="_compute_open_quantity",
        help="Ordered units not yet delivered.",
        digits="Product Unit",
    )
    quantity = fields.Float(
        string="Cancel", digits="Product Unit", help="Units to cancel."
    )

    @api.depends("sale_line_id.product_uom_qty", "sale_line_id.qty_delivered")
    def _compute_open_quantity(self) -> None:
        for line in self:
            sale_line = line.sale_line_id
            line.open_quantity = sale_line.product_uom_qty - sale_line.qty_delivered
