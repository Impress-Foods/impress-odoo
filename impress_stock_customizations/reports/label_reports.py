import markupsafe

from odoo import models


class ReportProductProductLabel2x4(models.AbstractModel):
    _inherit = "report.impress_stock_customizations.label_base"

    _name = "report.impress_stock_customizations.label_product_zpl_2x4"
    _description = "Product Label Report"

    def _get_report_values(self, docids, data):
        # The records come from docids: a caller that renders outside a view
        # action has an active_ids in context that is not the selection, and
        # preferring it printed whichever product that context happened to hold.
        products = self.env["product.product"].browse(docids)

        product_list = []
        for product in products:
            # Be tolerant to both str and int keys (JSON round-trip stringifies)
            product_values = data.get(str(product.id), data.get(product.id, {}))
            if not product_values:
                # Fallback to defaults when called without data (e.g. direct print)
                product_values = {}
            data_dict = self._build_label_record(
                product,
                product_values,
                product.display_name,
                product_id=product,
            )
            data_dict["product_record"] = product
            data_dict["product_quantity"] = data_dict.pop("product_qty")
            product_list.append(data_dict)

        return {"docs": product_list}


class ReportProductProductLabel4x6(models.AbstractModel):
    _inherit = "report.impress_stock_customizations.label_product_zpl_2x4"
    _name = "report.impress_stock_customizations.label_product_zpl_4x6"
    _description = "Product Label Report"


class ReportLotLabel2x4(models.AbstractModel):
    _inherit = "report.impress_stock_customizations.label_base"
    _name = "report.impress_stock_customizations.label_lot_zpl_2x4"
    _description = "Lot Label Report 2x4"

    def _get_report_values(self, docids, data):
        lots = self.env["stock.lot"].browse(docids)
        lot_list = []

        lots.ensure_one()

        for lot in lots:
            lot_values = data.get(str(lot.id), data.get(lot.id, {}))
            if not lot_values:
                lot_values = {}
            data_dict = self._build_label_record(
                lot,
                lot_values,
                lot.product_id.display_name,
                lot_id=lot,
            )
            data_dict["name"] = markupsafe.Markup(lot.name)
            data_dict["lot_record"] = lot
            lot_list.append(data_dict)

        return {"docs": lot_list}


class ReportLotLabel2x6(models.AbstractModel):
    _inherit = "report.impress_stock_customizations.label_lot_zpl_2x4"
    _name = "report.impress_stock_customizations.label_lot_zpl_4x6"
    _description = "Lot Label Report 4x6"
