import logging

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
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
                "type": "product",
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
                "type": "product",
                "tracking": "lot",
                "uom_id": cls.weight_uom_kg.id,
                "uom_po_id": cls.weight_uom_kg.id,
            }
        )

        cls.product_tracking_lot = cls.product_template_tracking_lot.product_variant_id

        cls.product_template_tracking_serial = cls.env["product.template"].create(
            {
                "name": "Product Serial Tracking",
                "barcode": "34567890123402",
                "type": "product",
                "tracking": "serial",
                "uom_id": cls.volume_uom_liter.id,
                "uom_po_id": cls.volume_uom_liter.id,
            }
        )
        cls.product_tracking_serial = (
            cls.product_template_tracking_serial.product_variant_id
        )

        cls.product_template_no_barcode = cls.env["product.template"].create(
            {
                "name": "Product No Barcode",
                "type": "product",
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
                "type": "product",
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

    def _assert_parsed_gs1(cls, barcode, expected):
        """Helper to verify that a GS1 barcode parses into expected values.
        expected: dict mapping AI to expected value (e.g. {'01': '...', '10': '...'})
        """
        parsed_results = cls.nomenclature.parse_barcode(barcode)
        parsed_dict = {res["ai"]: res["value"] for res in parsed_results}
        _logger.warning(parsed_dict)
        for ai, expected_val in expected.items():
            cls.assertIn(
                ai, parsed_dict, f"AI {ai} missing from parsed barcode {barcode}"
            )
            cls.assertEqual(
                parsed_dict[ai],
                expected_val,
                f"Value mismatch for AI {ai} in barcode {barcode}. "
                "Expected {expected_val}, got {parsed_dict[ai]}",
            )

    def test_barcode_gtin12_padding(cls):
        """Test that GTIN-12 is correctly padded to 14 digits"""
        # GTIN-12: 036000291452 -> 00036000291452
        barcode = cls.report._get_gs1_barcode(product_id=cls.product_gtin12)
        expected_padded = "00" + cls.product_gtin12.barcode
        cls.assertEqual(barcode, f"01{expected_padded}")
        cls._assert_parsed_gs1(barcode, {"01": expected_padded})

    def test_barcode_gtin13_padding(cls):
        """Test that GTIN-13 is correctly padded to 14 digits"""
        product_gtin13 = cls.env["product.product"].create(
            {
                "name": "GTIN-13 Product",
                "barcode": "1234567890128",
            }
        )
        barcode = cls.report._get_gs1_barcode(product_id=product_gtin13)
        expected_padded = "0" + product_gtin13.barcode
        cls.assertEqual(barcode, f"01{expected_padded}")
        cls._assert_parsed_gs1(barcode, {"01": expected_padded})

    def test_no_product_raises_error(cls):
        """Test that trying to generate a barcode without a product raises an error"""
        with cls.assertRaises(ValidationError):
            cls.report._get_gs1_barcode()

    def test_product_without_valid_ean_raises_error(cls):
        """Test that a product without a valid EAN raises an error"""
        with cls.assertRaises(ValidationError):
            cls.report._get_gs1_barcode(product_id=cls.product_no_barcode)

    def test_basic_barcode_no_quantity_no_lot(cls):
        """Test basic barcode generation with just a product"""
        barcode = cls.report._get_gs1_barcode(product_id=cls.product_tracking_none)
        cls.assertEqual(barcode, f"01{cls.product_tracking_none.barcode}")
        cls._assert_parsed_gs1(barcode, {"01": cls.product_tracking_none.barcode})

    def test_barcode_with_quantity_no_uom(cls):
        """Test barcode with quantity but no UoM"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_none, quantity=42
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_none.barcode}3000000042")
        cls._assert_parsed_gs1(
            barcode, {"01": cls.product_tracking_none.barcode, "30": 42}
        )

    def test_barcode_with_lot_tracking(cls):
        """Test barcode with lot tracking"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_lot,
            lot_id=cls.lot_lot,
            quantity=1,
            uom=cls.weight_uom_kg,
        )
        cls.assertEqual(
            barcode, f"01{cls.product_tracking_lot.barcode}31010000101024558"
        )
        cls._assert_parsed_gs1(
            barcode,
            {"01": cls.product_tracking_lot.barcode, "3101": 1.0, "10": "24558"},
        )

    def test_barcode_with_serial_tracking(cls):
        """Test barcode with serial tracking"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_serial,
            lot_id=cls.lot_serial,
            quantity=1,
            uom=cls.volume_uom_liter,
        )
        cls.assertEqual(
            barcode, f"01{cls.product_tracking_serial.barcode}31510000102187453"
        )
        cls._assert_parsed_gs1(
            barcode,
            {"01": cls.product_tracking_serial.barcode, "3151": 1.0, "21": "87453"},
        )

    def test_barcode_with_weight_kg(cls):
        """Test barcode with weight in kg"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_lot, quantity=1.5, uom=cls.weight_uom_kg
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_lot.barcode}3101000015")
        cls._assert_parsed_gs1(barcode, {"3101": 1.5})

    def test_barcode_with_weight_g(cls):
        """Test barcode with weight in grams (converted to kg)"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_lot,
            quantity=1500,  # 1500g = 1.5kg
            uom=cls.weight_uom_g,
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_lot.barcode}3101000015")
        cls._assert_parsed_gs1(barcode, {"3101": 1.5})

    def test_barcode_with_volume_liters(cls):
        """Test barcode with volume in liters"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_serial,
            quantity=1.5,
            uom=cls.volume_uom_liter,
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_serial.barcode}3151000015")
        cls._assert_parsed_gs1(barcode, {"3151": 1.5})

    def test_barcode_with_high_precision(cls):
        """Test barcode with high precision quantity"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_lot, quantity=1.234, uom=cls.weight_uom_kg
        )
        # 3102 means 2 decimals -> 1.23
        cls.assertEqual(barcode, f"01{cls.product_tracking_lot.barcode}3102000124")
        # Odoo's parser for 3102 will return 1.24
        cls._assert_parsed_gs1(barcode, {"3102": 1.24})

    def test_barcode_with_zero_quantity(cls):
        """Test barcode with zero quantity should not include quantity in barcode"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_none, quantity=0
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_none.barcode}")
        cls._assert_parsed_gs1(barcode, {"01": cls.product_tracking_none.barcode})
        parsed_results = cls.nomenclature.parse_barcode(barcode)
        ais = [res["ai"] for res in parsed_results]
        cls.assertNotIn("30", ais)

    def test_barcode_with_negative_quantity(cls):
        """Test barcode with negative quantity (should use absolute value)"""
        with cls.assertRaises(ValidationError):
            cls.report._get_gs1_barcode(
                product_id=cls.product_tracking_none, quantity=-5
            )

    def test_barcode_with_large_quantity(cls):
        """Test barcode with large quantity"""
        barcode = cls.report._get_gs1_barcode(
            product_id=cls.product_tracking_none, quantity=99999999
        )
        cls.assertEqual(barcode, f"01{cls.product_tracking_none.barcode}3099999999")
        cls._assert_parsed_gs1(barcode, {"30": 99999999})
