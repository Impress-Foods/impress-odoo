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
    def _make_variable_decimal_code(self, quantity: int | float, prefix: str) -> str:
        if isinstance(quantity, int):
            return prefix + pad_to_size(str(quantity), 6)

        split_number = str(quantity).split(".")
        int_part_length = len(split_number[0])
        dec_part_length = len(split_number[1])
        total_length = int_part_length + dec_part_length

        if total_length > 6:
            dec_part_length = 6 - int_part_length
            split_number[1] = split_number[1][:dec_part_length]

        quantity_barcode = f"{prefix}{dec_part_length}" + pad_to_size(
            str("".join(split_number)), 6
        )

        return quantity_barcode

    @api.model
    def _get_qty_barcode(self, quantity, uom):
        uom_type = uom.category_id.name if uom else "Unit"

        if uom:
            ref_unit = uom.category_id.uom_ids.filtered(
                lambda u: u.uom_type == "reference"
            )[:1]
            if ref_unit:
                quantity = uom._compute_quantity(
                    quantity, ref_unit, raise_if_failure=False
                )

        # Standard Odoo categories for weight and volume
        weight_categ = self.env.ref(
            "uom.product_uom_categ_kgm", raise_if_not_found=False
        )
        volume_categ = self.env.ref(
            "uom.product_uom_categ_vol", raise_if_not_found=False
        )

        if weight_categ and uom and uom.category_id == weight_categ:
            quantity_barcode = self._make_variable_decimal_code(quantity, "310")
        elif volume_categ and uom and uom.category_id == volume_categ:
            quantity_barcode = self._make_variable_decimal_code(quantity, "315")
        elif uom_type == "Weight":
            quantity_barcode = self._make_variable_decimal_code(quantity, "310")
        elif uom_type == "Volume":
            quantity_barcode = self._make_variable_decimal_code(quantity, "315")
        else:
            quantity_barcode = "30" + pad_to_size(str(int(quantity)), 8)

        return quantity_barcode

    @api.model
    def _get_gs1_barcode(
        self,
        product_id=None,
        lot_id=None,
        quantity: int | float = 0,
        uom=None,
        packaging_id=None,
        packaging_qty: int | float | None = None,
    ):
        if not product_id:
            raise ValidationError(_("Cannot create a GS1 barcode without a product"))

        if not product_id.valid_ean:
            raise ValidationError(
                _(f"Product {product_id.name} does not have a valid EAN")
            )

        barcode: str = product_id.barcode or ""
        if not barcode or not barcode.isnumeric():
            raise ValidationError(_(f"Barcode must be numeric: {barcode}"))
        if len(barcode) not in [12, 13, 14]:
            raise ValidationError(
                _(f"Invalid barcode length (must be 12, 13 or 14): {len(barcode)}")
            )

        product_barcode = "01" + pad_to_size(barcode, 14)
        lot_barcode = ""
        quantity_barcode = ""
        date_barcode = ""

        if quantity and quantity < 0:
            raise ValidationError(_("Quantity cannot be negative!"))

        if lot_id:
            if lot_id.product_id.tracking == "lot":
                lot_barcode = "10" + lot_id.name
            elif lot_id.product_id.tracking == "serial":
                lot_barcode = "21" + lot_id.name

            # Add expiration date (AI 17) or best before (AI 15)
            expiry_date = lot_id.expiration_date or lot_id.use_date
            if expiry_date:
                ai = "17" if lot_id.expiration_date else "15"
                date_barcode = ai + expiry_date.strftime("%y%m%d")

        if packaging_id:
            product_barcode = "01" + pad_to_size(packaging_id.barcode or "", 14)
            if packaging_qty:
                quantity = packaging_qty

        if quantity != 0:
            quantity_barcode = self._get_qty_barcode(quantity, uom)

        return product_barcode + quantity_barcode + date_barcode + lot_barcode


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

        return {
            "docs": lot_list,
        }


class ReportLotLabel2x6(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_lot_zpl_2x4"
    _name = "report.label_printing_wizard.label_lot_zpl_4x6"
    _description = "Lot Label Report 4x6"
