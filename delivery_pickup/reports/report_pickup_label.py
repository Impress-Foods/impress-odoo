import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ReportShippingLabel(models.AbstractModel):
    _name = "report.delivery_pickup.pickup_delivery_label"
    _description = "Model for pickup_delivery_label report"

    def _get_report_values(self, docids: list[int], data: dict) -> dict:
        pickings = self.env["stock.picking"].browse(docids)
        package_ids = {}

        for picking in pickings:
            _logger.warning(
                self.env["stock.package.history"].search(
                    [("picking_ids", "=", picking.id)]
                )
            )
            package_ids[picking.id] = self.env["stock.package.history"].search(
                [("picking_ids", "=", picking.id)]
            )

        return {"docs": pickings, "packages": package_ids}
