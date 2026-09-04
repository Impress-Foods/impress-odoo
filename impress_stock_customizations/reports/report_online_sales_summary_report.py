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
            carrier = getattr(picking, "carrier_id", False)
            order = getattr(picking, "sale_id", False)

            values = {
                "name": picking.display_name,
                "client": picking.partner_id.name,
                "carrier": carrier.name if carrier else "",
                "order": order.name if order else "",
            }

            _logger.debug(values)
            products_by_category = defaultdict(int)
            for line in picking.move_ids:
                products_by_category[line.product_category_id.name] += (
                    line.product_uom_qty
                )
            values["products_by_category"] = dict(sorted(products_by_category.items()))
            values["total"] = int(sum(products_by_category.values()))

            kits = defaultdict(float)
            for move in picking.move_ids:
                bom_line = move.bom_line_id
                if (
                    bom_line
                    and bom_line.bom_id
                    and len(bom_line.bom_id.bom_line_ids) > 1
                ):
                    kit_name = bom_line.bom_id.product_tmpl_id.name
                    kits[kit_name] = move.product_uom_qty / bom_line.product_qty
            values["kits"] = {k: int(v) for k, v in sorted(kits.items())}

            pickings.append(values)
        _logger.debug(pickings)
        return {
            "doc_ids": docids,
            "doc_model": self.env["stock.picking"],
            "docs": docs,
            "pickings": pickings,
        }
