import logging

import markupsafe

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def pad_to_size(string, size):
    return "0" * (size - len(string)) + string


def split_float(number: float):
    string_repr = str(number)
    return string_repr.split(".")


class ReportLabelBase(models.AbstractModel):
    _name = "report.label_printing_wizard.label_base"
    _description = "Label Base Report"

    def _get_report_values(self, docids, data):
        return {"docs": []}

    @api.model
    def _get_gs1_barcode(
        self,
        product_id=None,
        lot_id=None,
        quantity: int | float = 0,
        uom=None,
        packaging_id=None,
        packaging_qty: int | float = 0,
    ):
        if not product_id:
            raise ValidationError(_("Cannot create a GS1 barcode without a product"))

        if not product_id.valid_ean:
            raise ValidationError(
                _(f"Product {product_id.name} does not have a valid EAN")
            )

        product_barcode = "01" + product_id.barcode
        lot_barcode = ""
        quantity_barcode = ""

        if quantity and quantity < 0:
            raise ValidationError(_("Quantity cannot be negative!"))

        if lot_id:
            if lot_id.product_id.tracking == "lot":
                lot_barcode = "10" + lot_id.name
            elif lot_id.product_id.tracking == "serial":
                lot_barcode = "21" + lot_id.name

        if quantity != 0 and uom:
            ref_unit = self.env["uom.uom"].search(
                [
                    ("category_id", "=", uom.category_id.id),
                    ("uom_type", "=", "reference"),
                ]
            )

            quantity = uom._compute_quantity(quantity, ref_unit, raise_if_failure=False)
            match uom.category_id.name:
                case "Weight":
                    split_quantity = split_float(quantity)
                    n_decimals = len(split_quantity[1])
                    quantity_barcode = f"310{n_decimals}" + pad_to_size(
                        str("".join(split_quantity)), 6
                    )

                case "Volume":
                    split_quantity = split_float(quantity)
                    n_decimals = len(split_quantity[1])
                    quantity_barcode = f"315{n_decimals}" + pad_to_size(
                        str("".join(split_quantity)), 6
                    )

                case _:
                    quantity_barcode = "30" + pad_to_size(str(int(quantity)), 8)

        elif quantity != 0:
            quantity_barcode = "30" + pad_to_size(str(int(quantity)), 8)

        if packaging_id:
            product_barcode = "01" + packaging_id.barcode
            if packaging_qty != 0:
                quantity_barcode = "30" + pad_to_size(str(int(packaging_qty)), 8)

        return product_barcode + quantity_barcode + lot_barcode


class ReportProductProductLabel2x4(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_base"

    _name = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _description = "Product Label Report"

    def _get_report_values(self, docids, data):
        products = self.env["product.product"].browse(docids)

        product_list = []
        for product in products:
            packaging = False

            if "label_packaging_id" in self.env.context:
                packaging = self.env["product.packaging"].browse(
                    self.env.context.get("label_packaging_id")
                )

            data_dict = {
                "product_record": product,
                "display_name_markup": markupsafe.Markup(product.display_name),
                "product_quantity": self.env.context.get("label_product_qty", 0),
                "gs1_barcode": False,
                "label_count": self.env.context.get("label_count", False),
                "packaging_name": markupsafe.Markup(packaging.name)
                if packaging
                else False,
                "packaging_qty": self.env.context.get("label_packaging_qty", False),
            }

            if product.valid_ean:
                data_dict["gs1_barcode"] = self._get_gs1_barcode(
                    product_id=product,
                    quantity=self.env.context.get("label_product_qty", 0),
                    uom=product.uom_id,
                    packaging_id=packaging,
                    packaging_qty=self.env.context.get("label_packaging_qty", 0),
                )

            product_list.append(data_dict)

        _logger.warning(product_list)
        return {
            "docs": product_list,
        }


class ReportProductProductLabel4x6(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _name = "report.label_printing_wizard.label_product_product_zpl_4x6"
    _description = "Product Label Report"


class ReportLotLabel2x4(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_base"
    _name = "report.label_printing_wizard.label_lot_zpl_2x4"
    _description = "Lot Label Report 2x4"

    def _get_report_values(self, docids, data):
        lots = self.env["stock.lot"].browse(docids)
        lot_list = []

        for lot in lots:
            packaging = False

            if "label_packaging_id" in self.env.context:
                packaging = self.env["product.packaging"].browse(
                    self.env.context.get("label_packaging_id")
                )

            if "label_product_qty" in self.env.context and len(lots) != 1:
                raise UserError(_("Only one lot can be selected"))

            data_dict = {
                "display_name_markup": markupsafe.Markup(lot.product_id.display_name),
                "name": markupsafe.Markup(lot.name),
                "lot_record": lot,
                "gs1_barcode": False,
                "product_qty": self.env.context.get("label_product_qty", False),
                "packaging_name": markupsafe.Markup(packaging.name)
                if packaging
                else False,
                "packaging_qty": self.env.context.get("label_packaging_qty", False),
                "label_count": self.env.context.get("label_count", False),
            }

            if lot.product_id.valid_ean:
                data_dict["gs1_barcode"] = self._get_gs1_barcode(
                    product_id=lot.product_id,
                    lot_id=lot,
                    quantity=self.env.context.get("label_product_qty", 0),
                    uom=lot.product_id.uom_id,
                    packaging_id=packaging,
                    packaging_qty=self.env.context.get("label_packaging_qty", 0),
                )

            lot_list.append(data_dict)

        _logger.warning(lot_list)
        return {
            "docs": lot_list,
        }


class ReportLotLabel2x6(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_lot_zpl_2x4"
    _name = "report.label_printing_wizard.label_lot_zpl_4x6"
    _description = "Lot Label Report 4x6"
