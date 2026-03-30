import datetime
import logging
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import common

_logger = logging.getLogger(__name__)


class TestReportLabelBase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        uom = cls.env["uom.uom"]
        cls.unit_uom = uom.search([("name", "=", "Units")])
        cls.weight_uom_kg = uom.search([("name", "=", "kg")])
        cls.volume_uom_liter = uom.search([("name", "=", "L")])
        cls.weight_uom_g = uom.search([("name", "=", "g")])

        # Create products
        cls.product_template_tracking_none = cls.env["product.template"].create(
            {
                "name": "Product No Tracking",
                "barcode": "12345678901286",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": cls.unit_uom.id,
            }
        )

        cls.product_tracking_none = (
            cls.product_template_tracking_none.product_variant_id
        )

        cls.product_template_tracking_lot = cls.env["product.template"].create(
            {
                "name": "Product Lot Tracking",
                "barcode": "21098765432108",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
                "uom_id": cls.weight_uom_kg.id,
            }
        )

        cls.product_tracking_lot = cls.product_template_tracking_lot.product_variant_id

        cls.product_template_tracking_serial = cls.env["product.template"].create(
            {
                "name": "Product Serial Tracking",
                "barcode": "34567890123402",
                "type": "consu",
                "is_storable": True,
                "tracking": "serial",
                "uom_id": cls.volume_uom_liter.id,
            }
        )
        cls.product_tracking_serial = (
            cls.product_template_tracking_serial.product_variant_id
        )

        cls.product_template_no_barcode = cls.env["product.template"].create(
            {
                "name": "Product No Barcode",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": cls.unit_uom.id,
            }
        )
        cls.product_no_barcode = cls.product_template_no_barcode.product_variant_id

        # Create lots
        cls.lot_lot = cls.env["stock.lot"].create(
            {
                "name": "24558",
                "product_id": cls.product_tracking_lot.id,
                "company_id": cls.env.company.id,
            }
        )

        cls.lot_serial = cls.env["stock.lot"].create(
            {
                "name": "87453",
                "product_id": cls.product_tracking_serial.id,
                "company_id": cls.env.company.id,
            }
        )

        cls.product_template_gtin12 = cls.env["product.template"].create(
            {
                "name": "Product GTIN-12",
                "barcode": "036000291452",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": cls.unit_uom.id,
            }
        )
        cls.product_gtin12 = cls.product_template_gtin12.product_variant_id

        # Get the report model and nomenclature
        cls.report = cls.env["report.label_printing_wizard.label_base"]
        cls.nomenclature = cls.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )

    def _assert_parsed_gs1(cls, barcode, expected) -> None:
        """Helper to verify that a GS1 barcode parses into expected values.
        expected: dict mapping AI to expected value (e.g. {'01': '...', '10': '...'})
        """
        parsed_results = cls.nomenclature.parse_barcode(barcode)
        parsed_dict = {res["ai"]: res["value"] for res in parsed_results}
        for ai, expected_val in expected.items():
            cls.assertIn(
                ai, parsed_dict, f"AI {ai} missing from parsed barcode {barcode}"
            )
            cls.assertEqual(
                parsed_dict[ai],
                expected_val,
                f"Value mismatch for AI {ai} in barcode {barcode}. "
                f"Expected {expected_val}, got {parsed_dict[ai]}",
            )

    def test_barcode_gtin12_padding(self) -> None:
        """Test that GTIN-12 is correctly padded to 14 digits"""
        # GTIN-12: 036000291452 -> 00036000291452
        barcode = self.report._get_gs1_barcode(product_id=self.product_gtin12)
        expected_padded = "00" + self.product_gtin12.barcode
        self.assertEqual(barcode, f"01{expected_padded}")
        self._assert_parsed_gs1(barcode, {"01": expected_padded})

    def test_barcode_gtin13_padding(self) -> None:
        """Test that GTIN-13 is correctly padded to 14 digits"""
        product_gtin13 = self.env["product.product"].create(
            {
                "name": "GTIN-13 Product",
                "barcode": "1234567890128",
            }
        )
        barcode = self.report._get_gs1_barcode(product_id=product_gtin13)
        expected_padded = "0" + product_gtin13.barcode
        self.assertEqual(barcode, f"01{expected_padded}")
        self._assert_parsed_gs1(barcode, {"01": expected_padded})

    def test_no_product_raises_error(self) -> None:
        """Test that trying to generate a barcode without a product raises an error"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode()

    def test_product_without_valid_ean_raises_error(self) -> None:
        """Test that a product without a valid EAN raises an error"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode(product_id=self.product_no_barcode)

    def test_product_with_too_long_barcode_raises_error(self) -> None:
        product = self.env["product.product"].create(
            {
                "name": "Product Long Barcode",
                "barcode": "123456789101112",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": self.unit_uom.id,
            }
        )
        with self.assertRaisesRegex(
            ValidationError, "Product .* does not have a valid EAN"
        ):
            self.report._get_gs1_barcode(product_id=product)

    def test_product_with_too_short_barcode_raises_error(self) -> None:
        product = self.env["product.product"].create(
            {
                "name": "Product Short Barcode",
                "barcode": "12345678910",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": self.unit_uom.id,
            }
        )
        with self.assertRaisesRegex(
            ValidationError, "Product .* does not have a valid EAN"
        ):
            self.report._get_gs1_barcode(product_id=product)

    def test_basic_barcode_no_quantity_no_lot(self) -> None:
        """Test basic barcode generation with just a product"""
        barcode = self.report._get_gs1_barcode(product_id=self.product_tracking_none)
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}")
        self._assert_parsed_gs1(barcode, {"01": self.product_tracking_none.barcode})

    def test_barcode_with_quantity_no_uom(self) -> None:
        """Test barcode with quantity but no UoM"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=42
        )
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}3000000042")
        self._assert_parsed_gs1(
            barcode, {"01": self.product_tracking_none.barcode, "30": 42}
        )

    def test_barcode_with_lot_tracking(self) -> None:
        """Test barcode with lot tracking"""
        QTY = 1
        GTIN = "01" + self.product_tracking_lot.barcode
        LOT = "10" + self.lot_lot.name
        QTY_CODE = "3100" + str(QTY).zfill(6)
        EXPECTED = GTIN + QTY_CODE + LOT
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            lot_id=self.lot_lot,
            quantity=QTY,
            uom=self.weight_uom_kg,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(
            barcode,
            {
                "01": self.product_tracking_lot.barcode,
                "3100": QTY,
                "10": self.lot_lot.name,
            },
        )

    def test_barcode_with_serial_tracking(self) -> None:
        """Test barcode with serial tracking"""
        QTY = 1
        GTIN = "01" + self.product_tracking_serial.barcode
        QTY_CODE = "315" + "0" + str(QTY).zfill(6)
        SERIAL = "21" + self.lot_serial.name
        EXPECTED = GTIN + QTY_CODE + SERIAL

        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_serial,
            lot_id=self.lot_serial,
            quantity=QTY,
            uom=self.volume_uom_liter,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(
            barcode,
            {
                "01": self.product_tracking_serial.barcode,
                "3150": QTY,
                "21": self.lot_serial.name,
            },
        )

    def test_barcode_with_weight_kg(self) -> None:
        """Test barcode with weight in kg"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot, quantity=1.5, uom=self.weight_uom_kg
        )
        self.assertEqual(barcode, f"01{self.product_tracking_lot.barcode}3101000015")
        self._assert_parsed_gs1(barcode, {"3101": 1.5})

    def test_barcode_with_volume_liters(self) -> None:
        """Test barcode with volume in liters"""
        GTIN = "01" + self.product_tracking_serial.barcode
        EXPECTED = GTIN + "315" + "1" + "000015"
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_serial,
            quantity=1.5,
            uom=self.volume_uom_liter,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(barcode, {"3151": 1.5})

    def test_barcode_with_high_precision(self) -> None:
        """Test barcode with high precision quantity"""
        GTIN = "01" + self.product_tracking_lot.barcode
        EXPECTED = GTIN + "310" + "3" + "001234"
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot, quantity=1.234, uom=self.weight_uom_kg
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(barcode, {"3103": 1.234})

    def test_barcode_with_very_high_precision(self) -> None:
        """Test barcode with very high precision quantity"""
        GTIN = "01" + self.product_tracking_lot.barcode
        EXPECTED = GTIN + "310" + "5" + "123456"
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            quantity=1.234567,
            uom=self.weight_uom_kg,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(barcode, {"3105": 1.23456})

    def test_barcode_with_no_int_part(self) -> None:
        """Test barcode with very high precision quantity"""
        GTIN = "01" + self.product_tracking_lot.barcode
        EXPECTED = GTIN + "310" + "5" + "012345"
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            quantity=0.12345,
            uom=self.weight_uom_kg,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(barcode, {"3105": 0.12345})

    def test_barcode_with_zero_quantity(self) -> None:
        """Test barcode with zero quantity should not include quantity in barcode"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=0
        )
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}")
        self._assert_parsed_gs1(barcode, {"01": self.product_tracking_none.barcode})
        parsed_results = self.nomenclature.parse_barcode(barcode)
        ais = [res["ai"] for res in parsed_results]
        self.assertNotIn("30", ais)

    def test_barcode_with_negative_quantity(self) -> None:
        """Test barcode with negative quantity (should use absolute value)"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode(
                product_id=self.product_tracking_none, quantity=-5
            )

    def test_barcode_with_expiration_date(self) -> None:
        """Test barcode with expiration date (AI 17)"""
        PADDED_BARCODE = self.product_tracking_lot.barcode.zfill(14)
        GTIN = "01" + PADDED_BARCODE
        QTY = "310" + "0" + "000001"
        LOT = "10" + self.lot_lot.name
        DATE = "17" + "261231"
        EXPECTED = GTIN + QTY + DATE + LOT
        expiry = datetime.date(2026, 12, 31)
        self.lot_lot.expiration_date = expiry
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            lot_id=self.lot_lot,
            quantity=1,
            uom=self.weight_uom_kg,
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(
            barcode,
            {"01": PADDED_BARCODE, "3100": 1, "10": self.lot_lot.name, "17": expiry},
        )

    def test_barcode_with_large_quantity(self) -> None:
        """Test barcode with large quantity"""
        QTY = 99999999
        GTIN = "01" + self.product_tracking_none.barcode
        EXPECTED = GTIN + "30" + str(QTY)
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=QTY
        )
        self.assertEqual(barcode, EXPECTED)
        self._assert_parsed_gs1(barcode, {"30": QTY})

    def test_get_qty_barcode_no_uom(self) -> None:
        QTY = 10.5
        EXPECTED = "30" + "00000010"

        result = self.report._get_qty_barcode(QTY)
        self.assertEqual(result, EXPECTED)

    def test_get_qty_barcode_unit_uom(self) -> None:
        QTY = 10.5
        UOM = self.unit_uom
        EXPECTED = "30" + "00000010"

        result = self.report._get_qty_barcode(QTY, UOM)
        self.assertEqual(result, EXPECTED)

    def test_get_qty_barcode_int(self) -> None:
        PREFIX = "310"
        EXPECTED = PREFIX + "0" + "000100"  # AI + precision + 6 digit for value
        barcode = self.report._make_variable_decimal_code(100, "310")
        self.assertEqual(barcode, EXPECTED)

    def test_get_qty_barcode_float_one_decimal(self) -> None:
        PREFIX = "310"
        EXPECTED = PREFIX + "1" + "000105"  # AI + precision + 6 digit for value
        barcode = self.report._make_variable_decimal_code(10.5, "310")
        self.assertEqual(barcode, EXPECTED)

    def test_get_qty_barcode_float_two_decimal(self) -> None:
        PREFIX = "310"
        EXPECTED = PREFIX + "2" + "000555"  # AI + precision + 6 digit for value
        barcode = self.report._make_variable_decimal_code(5.55, "310")
        self.assertEqual(barcode, EXPECTED)

    def test_get_closest_uom_reference_exact_match(self) -> None:
        result = self.report._get_closest_uom_reference(self.unit_uom)
        self.assertIsNotNone(result)
        uom, uom_ref = result
        self.assertEqual(uom.id, self.unit_uom.id)
        self.assertEqual(uom_ref, "uom.product_uom_unit")

    def test_get_closest_uom_reference_kg(self) -> None:
        result = self.report._get_closest_uom_reference(self.weight_uom_kg)
        self.assertIsNotNone(result)
        uom, uom_ref = result
        self.assertEqual(uom.id, self.weight_uom_kg.id)
        self.assertEqual(uom_ref, "uom.product_uom_kgm")

    def test_get_closest_uom_reference_liter(self) -> None:
        result = self.report._get_closest_uom_reference(self.volume_uom_liter)
        self.assertIsNotNone(result)
        uom, uom_ref = result
        self.assertEqual(uom.id, self.volume_uom_liter.id)
        self.assertEqual(uom_ref, "uom.product_uom_litre")

    def test_get_closest_uom_reference_gram(self) -> None:
        result = self.report._get_closest_uom_reference(self.weight_uom_g)
        self.assertIsNotNone(result)
        uom, uom_ref = result
        self.assertEqual(uom.id, self.weight_uom_kg.id)
        self.assertEqual(uom_ref, "uom.product_uom_kgm")

    def test_get_closest_uom_reference_no_parent_path(self) -> None:
        uom_no_parent = self.env["uom.uom"].create(
            {
                "name": "Test UOM No Parent",
                "factor": 1.0,
            }
        )
        result = self.report._get_closest_uom_reference(uom_no_parent)
        self.assertIsNone(result)

    def test_get_closest_uom_reference_none_input(self) -> None:
        result = self.report._get_closest_uom_reference(None)
        self.assertIsNone(result)

    def test_prepare_label_data_valid(self) -> None:
        PRODUCT = self.product_tracking_none
        QTY = 10
        UOM = self.unit_uom
        LABEL_COUNT = 2
        data = self.report._prepare_label_data(PRODUCT, QTY, UOM, LABEL_COUNT)

        self.assertEqual(data["label_count"], LABEL_COUNT)
        self.assertEqual(data["qty"], QTY)
        self.assertEqual(data["unit_type"], "uom.product_uom_unit")

    def test_prepare_label_data_no_uom(self) -> None:
        PRODUCT = self.product_tracking_none
        QTY = 10
        UOM = None
        LABEL_COUNT = 2
        data = self.report._prepare_label_data(PRODUCT, QTY, UOM, LABEL_COUNT)

        self.assertEqual(data["label_count"], LABEL_COUNT)
        self.assertFalse(data.get("qty", False))
        self.assertFalse(data.get("unit_type", False))

    @patch(
        "odoo.addons.label_printing_wizard.reports.labels.ReportLabelBase._get_closest_uom_reference"
    )
    def test_prepare_label_data_no_closest_uom(
        self, mock_get_closest_uom_reference
    ) -> None:
        PRODUCT = self.product_tracking_none
        QTY = 10
        UOM = self.unit_uom
        LABEL_COUNT = 2

        mock_get_closest_uom_reference.return_value = False

        with self.assertRaisesRegex(ValidationError, "Could not find base unit"):
            self.report._prepare_label_data(PRODUCT, QTY, UOM, LABEL_COUNT)
