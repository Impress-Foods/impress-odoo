from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sale.models.sale_order_line import SaleOrderLine

COSTCO_INTAKE = "edi.rithum.costco.intake"  # the model that reads Costco's files


class SaleOrder(models.Model):
    _inherit = "sale.order"

    costco_shipping_method = fields.Char(
        readonly=True,
        copy=False,
        help="Carrier and service Costco asked for (TD505 of the 850). It is "
        "repeated on the shipment confirmation.",
    )

    rithum_partner_id = fields.Many2one(
        "edi.rithum.partner",
        string="Rithum partner",
        index=True,
        copy=False,
        readonly=True,
        ondelete="restrict",
        help="The retailer whose file created the order. It is kept on the order "
        "itself: the exchange record can be deleted by the backend's retention.",
    )

    costco_can_cancel = fields.Boolean(
        compute="_compute_costco_can_cancel",
        help="An order from Costco, not cancelled, with units not yet delivered.",
    )

    @api.depends("state", "rithum_partner_id.intake_model", "order_line.qty_delivered")
    def _compute_costco_can_cancel(self) -> None:
        for order in self:
            order.costco_can_cancel = (
                order.state != "cancel"
                and order._costco_is_order()
                and any(order._costco_open_lines())
            )

    def action_cancel(self) -> bool:
        """Extends sale.order.action_cancel: refuse to cancel what Costco is owed.

        The standard button would drop open Costco lines without telling Costco.
        "Cancel with Costco" cancels the order itself (_action_cancel) after
        sending the reason, so it is not affected.
        """
        if any(order.costco_can_cancel for order in self):
            raise UserError(
                self.env._(
                    "This Costco order has units still to deliver: use "
                    '"Cancel with Costco" so that Costco is told and given a reason.'
                )
            )
        return super().action_cancel()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_costco_order(self) -> None:
        """A Costco order is a record of what was promised.

        Deleting it would drop units Costco was never told about. Cancel it with
        Costco instead. This runs before sale.order.unlink deletes anything.
        """
        if any(order._costco_is_order() for order in self):
            raise UserError(
                self.env._("A Costco order cannot be deleted: cancel it with Costco.")
            )

    def _costco_is_order(self) -> bool:
        """Whether this order was created from a file received from Costco.

        An empty recordset, such as the order of a delivery without one, is not.
        """
        return self.rithum_partner_id.intake_model == COSTCO_INTAKE

    def _costco_open_lines(self) -> SaleOrderLine:
        """Costco lines with units still to deliver."""
        return self.order_line.filtered(
            lambda line: line.costco_sku and line.product_uom_qty > line.qty_delivered
        )

    def action_costco_cancel(self) -> dict:
        """Open a cancellation of this order, with every open Costco line listed."""
        self.ensure_one()
        if not self.costco_can_cancel:
            raise UserError(self.env._("There is nothing to cancel on this order."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Cancel with Costco"),
            "res_model": "edi.rithum.costco.cancellation",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_line_ids": [
                    (0, 0, {"sale_line_id": line.id})
                    for line in self._costco_open_lines()
                ],
            },
        }
