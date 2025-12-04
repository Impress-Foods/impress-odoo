import logging

from odoo import api, models
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.mrp.models.stock_orderpoint import StockWarehouseOrderpoint

from .procurement import Procurement

_logger = logging.getLogger(__name__)


class ProcurementGroupInherit(models.Model):
    _inherit = "procurement.group"

    @api.model
    def run(self, procurements, raise_user_error=True):
        new_procurements = self.split_manufacturing_orders(procurements)
        return super().run(new_procurements, raise_user_error)

    @api.model
    def split_manufacturing_orders(self, procurements: list[Procurement]):
        new_procurements: list[Procurement] = []
        _logger.warning(f"procurement group: {procurements}")
        for procurement in procurements:
            orderpoint: StockWarehouseOrderpoint = procurement.values["orderpoint_id"]

            if orderpoint.qty_batch != 0:
                batch_size = orderpoint.qty_batch
                qty_left = procurement.product_qty

                while float_compare(qty_left, batch_size, precision_digits=2) >= 0:
                    proc = procurement._replace(product_qty=batch_size)
                    new_procurements.append(proc)
                    qty_left -= batch_size

                if not float_is_zero(qty_left, precision_digits=2):
                    proc = procurement._replace(product_qty=qty_left)
                    new_procurements.append(proc)
            else:
                new_procurements.append(procurement)

        return new_procurements
