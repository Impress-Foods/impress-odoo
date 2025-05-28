import logging

import markupsafe

from odoo import models

_logger = logging.getLogger(__name__)


class ReportProductProductLabel2x4(models.AbstractModel):
    _name = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _description = "Product Label Report"

    def _get_report_values(self, docids, data):
        products = self.env["product.product"].browse(docids)

        product_list = []
        for product in products:
            product_list.append(
                {
                    "product_record": product,
                    "display_name_markup": markupsafe.Markup(product.display_name),
                    "product_quantity": self.env.context.get("label_product_qty", 0),
                }
            )
        if "label_count" in self.env.context:
            product_list[0]["label_count"] = self.env.context.get("label_count")
        return {
            "docs": product_list,
        }


class ReportProductProductLabel4x6(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _name = "report.label_printing_wizard.label_product_product_zpl_4x6"
    _description = "Product Label Report"
