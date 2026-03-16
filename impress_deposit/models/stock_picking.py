import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    container_qty = fields.Integer(
        "Number of containers shipped", compute="_compute_container_qty", store=True
    )

    @api.depends(
        "move_line_ids",
        "move_line_ids.state",
        "move_line_ids.quantity",
        "move_line_ids.product_id.requires_deposit",
        "move_line_ids.product_id.qty_multiple",
    )
    def _compute_container_qty(self):
        for record in self:
            if not record.partner_id.requires_deposit:
                record.container_qty = 0
                continue

            record.container_qty = sum(
                record.move_line_ids.filtered(
                    lambda line: (
                        line.state == "done" and line.product_id.requires_deposit
                    )
                ).mapped(lambda line: line.quantity * line.product_id.qty_multiple)
            )

    def _action_done(self):
        result = super()._action_done()

        for picking in self.filtered(lambda pick: pick.container_qty != 0):
            sale_order = picking.sale_id
            if not sale_order or not sale_order.deposit_line_id:
                continue
            deposit_line = sale_order.deposit_line_id
            deposit_line.write(
                {"qty_delivered": deposit_line.qty_delivered + picking.container_qty}
            )

        return result
