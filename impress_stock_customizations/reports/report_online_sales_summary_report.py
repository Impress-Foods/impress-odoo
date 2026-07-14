import logging
from collections import defaultdict

from odoo import api, models

_logger = logging.getLogger(__name__)


class OnlineSalesSummaryReport(models.AbstractModel):
    _name = "report.impress_stock_customizations.online_sales_summary"
    _description = "Online Sales Summary Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["stock.picking"].browse(docids)
        pickings = []
        for picking in docs:
            values = {
                "name": picking.display_name,
                "carrier": picking.carrier_id.name,
                "client": picking.partner_id.name,
                "order": picking.sale_id.name,
            }
            products_by_category = defaultdict(int)
            for line in picking.move_ids:
                products_by_category[line.product_category_id.name] += (
                    line.product_uom_qty
                )
            values["products_by_category"] = dict(sorted(products_by_category.items()))
            values["total"] = int(sum(products_by_category.values()))
            pickings.append(values)
        _logger.debug(pickings)
        return {
            "doc_ids": docids,
            "doc_model": self.env["stock.picking"],
            "docs": docs,
            "pickings": pickings,
        }
