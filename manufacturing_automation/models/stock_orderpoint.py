import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockOrderPoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    qty_batch = fields.Float()

    @api.constrains("qty_batch")
    def _check_qty_batch(self):
        for record in self:
            if record.qty_batch < 0:
                raise ValidationError(self.env._("The batch size cannot be negative!"))
