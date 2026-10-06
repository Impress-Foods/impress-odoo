from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    delivered_gross_weight = fields.Float(compute="_compute_delivered_gross_weight")
    ordered_gross_weight = fields.Float(compute="_compute_ordered_gross_weight")

    delivered_net_weight = fields.Float(compute="_compute_delivered_net_weight")
    ordered_net_weight = fields.Float(compute="_compute_ordered_net_weight")

    @api.depends("product_id", "product_uom_qty")
    def _compute_ordered_gross_weight(self):
        for rec in self:
            rec.ordered_gross_weight = rec.product_id.weight * rec.product_uom_qty

    @api.depends("product_id", "qty_delivered")
    def _compute_delivered_gross_weight(self):
        for rec in self:
            rec.delivered_gross_weight = rec.product_id.weight * rec.qty_delivered

    @api.depends("product_id", "product_uom_qty")
    def _compute_ordered_net_weight(self):
        for rec in self:
            rec.ordered_net_weight = rec.product_id.net_weight * rec.product_uom_qty

    @api.depends("product_id", "qty_delivered")
    def _compute_delivered_net_weight(self):
        for rec in self:
            rec.delivered_net_weight = rec.product_id.net_weight * rec.qty_delivered

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        """Keep the pending delivery in sync when the ordered quantity changes.

        Extends ``sale.order.line._action_launch_stock_rule``. The standard
        implementation launches a procurement for the delta, which creates an
        extra picking when the quantity increases and a return from the
        customer location when it decreases. When the quantity of a confirmed
        line changes, we instead update the demand of the moves that are not
        validated yet, so no extra transfer is created.

        As soon as a move has been validated (``state == 'done'``), the
        standard behaviour is preserved: delivered goods cannot be reworked in
        place, they must be returned.
        """
        if self.env.context.get("skip_procurement") or not previous_product_uom_qty:
            # Initial confirmation, a new line added on a confirmed order, or
            # an explicit procurement skip: let the standard flow run.
            return super()._action_launch_stock_rule(
                previous_product_uom_qty=previous_product_uom_qty
            )

        lines_to_launch = self.env["sale.order.line"]
        for line in self:
            line = line.with_company(line.company_id)
            if not line._apply_qty_change_on_pending_moves():
                lines_to_launch |= line

        if lines_to_launch:
            return super(SaleOrderLine, lines_to_launch)._action_launch_stock_rule(
                previous_product_uom_qty=previous_product_uom_qty
            )
        return True

    def _apply_qty_change_on_pending_moves(self):
        """Apply the ordered quantity to the line's pending moves.

        :return: ``True`` when the change was fully applied to the existing
            moves, ``False`` when the standard procurement flow must run
            instead.
        :rtype: bool
        """
        self.ensure_one()
        if (
            self.state != "sale"
            or self.order_id.locked
            or self.product_id.type != "consu"
        ):
            return False

        outgoing_moves, incoming_moves = self._get_outgoing_incoming_moves(strict=False)
        # Without an outgoing move there is nothing to update in place, and a
        # return already in progress must keep going through the standard flow.
        if not outgoing_moves or incoming_moves:
            return False
        # Once a move is validated, the picking cannot be reworked in place.
        if outgoing_moves.filtered(lambda move: move.state == "done"):
            return False

        precision = self.env["decimal.precision"].precision_get("Product Unit")
        current_qty = self._get_qty_procurement()
        delta = self.product_uom_qty - current_qty
        if float_compare(delta, 0.0, precision_digits=precision) == 0:
            return True

        if delta > 0:
            self._add_demand_to_move(outgoing_moves[0], delta)
        else:
            self._remove_demand_from_moves(outgoing_moves, -delta)
        return True

    def _add_demand_to_move(self, move, qty):
        """Add ``qty`` (expressed in the line UoM) to ``move``'s demand."""
        self.ensure_one()
        move.product_uom_qty += self.product_uom_id._compute_quantity(
            qty, move.product_uom, rounding_method="HALF-UP"
        )

    def _remove_demand_from_moves(self, moves, qty):
        """Remove ``qty`` (expressed in the line UoM) from ``moves``.

        Moves are consumed from the most recent one, and their demand is never
        allowed to go below zero.
        """
        self.ensure_one()
        remaining = qty
        for move in moves.sorted("id", reverse=True):
            move_qty = move.product_uom._compute_quantity(
                move.product_uom_qty, self.product_uom_id, rounding_method="HALF-UP"
            )
            if (
                float_compare(
                    move_qty, remaining, precision_rounding=self.product_uom_id.rounding
                )
                <= 0
            ):
                move.product_uom_qty = 0.0
                remaining -= move_qty
            else:
                move.product_uom_qty = self.product_uom_id._compute_quantity(
                    move_qty - remaining,
                    move.product_uom,
                    rounding_method="HALF-UP",
                )
                remaining = 0.0
            if float_is_zero(
                remaining, precision_rounding=self.product_uom_id.rounding
            ):
                break
