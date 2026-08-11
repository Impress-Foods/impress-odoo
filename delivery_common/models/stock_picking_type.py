import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    auto_print_delivery_label = fields.Boolean(
        help="""If checked, the delivery label will be printed
        automatically when the picking is validated.""",
        default=False,
    )

    auto_print_instructions_label = fields.Boolean(
        help="""If checked, the instructions label will be printed
        automatically when the picking is validated.""",
        default=False,
    )
