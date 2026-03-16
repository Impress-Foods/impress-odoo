import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    container_qty = fields.Integer(
        "Number of containers shipped", compute="_compute_container_qty", store=True
    )

    @api.depends("move_line_ids", "move_line_ids.state")
    def _compute_container_qty(self):
        for record in self:
            total = 0
            if record.partner_id.requires_deposit:
                for line in record.move_line_ids:
                    total += line.container_qty

            record.container_qty = total
