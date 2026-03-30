import logging

import markupsafe

from odoo import api, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.stock.models.stock_lot import StockLot
from odoo.addons.uom.models.uom_uom import UomUom

_logger = logging.getLogger(__name__)


def pad_to_size(string, size):
    return "0" * (size - len(string)) + string


class ReportLabelBase(models.AbstractModel):
    _name = "report.label_printing_wizard.label_base"
    _description = "Label Base Report"

    UOM_UNIT = "uom.product_uom_unit"
    UOM_KGM = "uom.product_uom_kgm"
    UOM_LITRE = "uom.product_uom_litre"
    UOM_GRAM = "uom.product_uom_gram"
    UOM_MILLILITER = "uom.product_uom_milliliter"

    GS1_REFERENCE_FALLBACKS = {
        UOM_GRAM: UOM_KGM,
        UOM_MILLILITER: UOM_LITRE,
    }

    @api.model
    def _get_reference_uoms(self) -> list:
        return [
            (self.UOM_UNIT, self.env.ref(self.UOM_UNIT)),
            (self.UOM_KGM, self.env.ref(self.UOM_KGM)),
            (self.UOM_LITRE, self.env.ref(self.UOM_LITRE)),
        ]

    @api.model
    def _get_closest_uom_reference(
        self, target_uom: UomUom
    ) -> tuple[UomUom, str] | None:
        if not target_uom:
            return None

        path_ids = [int(x) for x in target_uom.parent_path.strip("/").split("/") if x]

        if not path_ids:
            return None

        best_match = None
        best_index = -1

        for uom_ref_str, ref_uom in self._get_reference_uoms():
            try:
                idx = path_ids.index(ref_uom.id)
                if idx > best_index:
                    best_index = idx
                    best_match = (ref_uom, uom_ref_str)
            except ValueError:
                continue

        target_xml_id = target_uom.get_external_id().get(target_uom.id, "")

        if not best_match:
            if target_xml_id in self.GS1_REFERENCE_FALLBACKS:
                fallback_xml_id = self.GS1_REFERENCE_FALLBACKS[target_xml_id]
                fallback_uom = self.env.ref(fallback_xml_id)
                return (fallback_uom, fallback_xml_id)
            return None

        ref_uom, ref_str = best_match

        return best_match

    @api.model
    def _prepare_label_data(
        self,
        record: StockLot | ProductProduct,
        product_uom_qty: float = 0,
        product_uom_id: UomUom = None,
        label_count: int = 1,
    ) -> dict:
        data = {
            "label_count": label_count,
        }

        if product_uom_id and product_uom_qty != 0:
            result = self._get_closest_uom_reference(product_uom_id)
            if not result:
                raise ValidationError(
                    self.env._(
                        "Could not find base unit for %s",
                        product_uom_id.display_name,
                    )
                )

            unit, unit_type = result

            data["qty"] = product_uom_id._compute_quantity(product_uom_qty, unit)
            data["unit_type"] = unit_type
        return data

    @api.model
    def _make_variable_decimal_code(self, quantity: int | float, prefix: str) -> str:
        if isinstance(quantity, int):
            return prefix + "0" + pad_to_size(str(quantity), 6)

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
    def _get_qty_barcode(self, quantity: float, uom: UomUom = None) -> str:
        if not uom:
            return "30" + pad_to_size(str(int(quantity)), 8)

        kg_uom: UomUom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        liter_uom: UomUom = self.env.ref(
            "uom.product_uom_litre", raise_if_not_found=False
        )

        match uom.id:
            case kg_uom.id:
                return self._make_variable_decimal_code(quantity, "310")
            case liter_uom.id:
                return self._make_variable_decimal_code(quantity, "315")
            case _:
                return "30" + pad_to_size(str(int(quantity)), 8)

    @api.model
    def _get_gs1_barcode(
        self,
        product_id: ProductProduct = None,
        lot_id: StockLot = None,
        quantity: int | float = 0,
        uom: UomUom = None,
        packaging_qty: int | float | None = None,
    ):
        if not product_id:
            raise ValidationError(
                self.env._("Cannot create a GS1 barcode without a product")
            )

        # Covers empty barcodes, too long and too short
        if not product_id.valid_ean:
            raise ValidationError(
                self.env._(
                    "Product %s does not have a valid EAN", product_id.display_name
                )
            )

        barcode: str = product_id.barcode or ""

        product_barcode = "01" + pad_to_size(barcode, 14)
        lot_barcode = ""
        quantity_barcode = ""
        date_barcode = ""

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

        if quantity and quantity < 0:
            raise ValidationError(self.env._("Quantity cannot be negative!"))

        if quantity:
            quantity_barcode = self._get_qty_barcode(quantity, uom)

        return product_barcode + quantity_barcode + date_barcode + lot_barcode

    @api.model
    def _build_label_record(
        self,
        record,
        data_dict: dict,
        display_name: str,
        product_id: ProductProduct = None,
        lot_id: StockLot = None,
    ) -> dict:
        label_data = self._prepare_label_data(
            record,
            product_uom_qty=data_dict.get("product_uom_qty", 0),
            product_uom_id=self.env["uom.uom"].browse(data_dict.get("product_uom_id"))
            if data_dict.get("product_uom_id")
            else None,
            label_count=data_dict.get("label_count", 1),
        )

        uom_ref = label_data.get("unit_type", self.UOM_UNIT)
        uom = self.env.ref(uom_ref)
        quantity = label_data.get("qty", 0)

        result = {
            "display_name_markup": markupsafe.Markup(display_name),
            "product_qty": quantity,
            "product_uom": uom,
            "gs1_barcode": False,
            "label_count": label_data.get("label_count", 1),
        }

        if product_id is None and lot_id:
            product_id = lot_id.product_id

        if product_id and product_id.valid_ean:
            result["gs1_barcode"] = self._get_gs1_barcode(
                product_id=product_id,
                lot_id=lot_id,
                quantity=quantity,
                uom=uom,
            )

        return result


class ReportProductProductLabel2x4(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_base"

    _name = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _description = "Product Label Report"

    def _get_report_values(self, docids, data):
        res_ids = self.env.context.get("active_ids", docids)
        products = self.env["product.product"].browse(res_ids)

        product_list = []
        for product in products:
            product_values = data[str(product.id)]
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
    _inherit = "report.label_printing_wizard.label_product_product_zpl_2x4"
    _name = "report.label_printing_wizard.label_product_product_zpl_4x6"
    _description = "Product Label Report"


class ReportLotLabel2x4(models.AbstractModel):
    _inherit = "report.label_printing_wizard.label_base"
    _name = "report.label_printing_wizard.label_lot_zpl_2x4"
    _description = "Lot Label Report 2x4"

    def _get_report_values(self, docids, data):
        res_ids = self.env.context.get("active_ids", docids)

        lots = self.env["stock.lot"].browse(res_ids)
        lot_list = []

        for lot in lots:
            if "label_product_qty" in self.env.context and len(lots) != 1:
                raise UserError(self.env._("Only one lot can be selected"))

            lot_values = data[str(lot.id)]
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
    _inherit = "report.label_printing_wizard.label_lot_zpl_2x4"
    _name = "report.label_printing_wizard.label_lot_zpl_4x6"
    _description = "Lot Label Report 4x6"
