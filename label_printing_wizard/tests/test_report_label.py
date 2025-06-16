import logging

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestReportLabelBase(common.TransactionCase):
    def setUp(self):
        super().setUp()

        uom = self.env["uom.uom"]
        self.unit_uom = uom.search([("name", "=", "Units")])
        self.weight_uom_kg = uom.search([("name", "=", "kg")])
        self.volume_uom_liter = uom.search([("name", "=", "L")])
        self.weight_uom_g = uom.search([("name", "=", "g")])

        # Create products
        self.product_template_tracking_none = self.env["product.template"].create(
            {
                "name": "Product No Tracking",
                "barcode": "12345678901286",
                "type": "consu",
                "tracking": "none",
                "uom_id": self.unit_uom.id,
            }
        )

        self.product_tracking_none = (
            self.product_template_tracking_none.product_variant_id
        )

        self.product_template_tracking_lot = self.env["product.template"].create(
            {
                "name": "Product Lot Tracking",
                "barcode": "21098765432108",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
                "uom_id": self.weight_uom_kg.id,
                "uom_po_id": self.weight_uom_kg.id,
            }
        )

        self.product_tracking_lot = (
            self.product_template_tracking_lot.product_variant_id
        )

        self.product_template_tracking_serial = self.env["product.template"].create(
            {
                "name": "Product Serial Tracking",
                "barcode": "34567890123402",
                "type": "consu",
                "is_storable": True,
                "tracking": "serial",
                "uom_id": self.volume_uom_liter.id,
                "uom_po_id": self.volume_uom_liter.id,
            }
        )
        self.product_tracking_serial = (
            self.product_template_tracking_serial.product_variant_id
        )

        self.product_template_no_barcode = self.env["product.template"].create(
            {
                "name": "Product No Barcode",
                "type": "consu",
                "is_storable": True,
                "tracking": "none",
                "uom_id": self.unit_uom.id,
            }
        )
        self.product_no_barcode = self.product_template_no_barcode.product_variant_id

        # Create lots
        self.lot_lot = self.env["stock.lot"].create(
            {
                "name": "24558",
                "product_id": self.product_tracking_lot.id,
                "company_id": self.env.company.id,
            }
        )

        self.lot_serial = self.env["stock.lot"].create(
            {
                "name": "87453",
                "product_id": self.product_tracking_serial.id,
                "company_id": self.env.company.id,
            }
        )

        # Get the report model
        self.report = self.env["report.label_printing_wizard.label_base"]

    def test_no_product_raises_error(self):
        """Test that trying to generate a barcode without a product raises an error"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode()

    def test_product_without_valid_ean_raises_error(self):
        """Test that a product without a valid EAN raises an error"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode(product_id=self.product_no_barcode)

    def test_basic_barcode_no_quantity_no_lot(self):
        """Test basic barcode generation with just a product"""
        barcode = self.report._get_gs1_barcode(product_id=self.product_tracking_none)
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}")

    def test_barcode_with_quantity_no_uom(self):
        """Test barcode with quantity but no UoM"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=42
        )
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}3000000042")

    def test_barcode_with_lot_tracking(self):
        """Test barcode with lot tracking"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            lot_id=self.lot_lot,
            quantity=1,
            uom=self.weight_uom_kg,
        )
        self.assertEqual(
            barcode, f"01{self.product_tracking_lot.barcode}31010000101024558"
        )

    def test_barcode_with_serial_tracking(self):
        """Test barcode with serial tracking"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_serial,
            lot_id=self.lot_serial,
            quantity=1,
            uom=self.volume_uom_liter,
        )
        self.assertEqual(
            barcode, f"01{self.product_tracking_serial.barcode}31010000102187453"
        )

    def test_barcode_with_weight_kg(self):
        """Test barcode with weight in kg"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot, quantity=1.5, uom=self.weight_uom_kg
        )
        self.assertEqual(barcode, f"01{self.product_tracking_lot.barcode}3101000015")

    def test_barcode_with_weight_g(self):
        """Test barcode with weight in grams (converted to kg)"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            quantity=1500,  # 1500g = 1.5kg
            uom=self.weight_uom_g,
        )
        # Should be the same as test_barcode_with_weight_kg
        # since we convert to reference UoM (kg)
        self.assertEqual(barcode, f"01{self.product_tracking_lot.barcode}3101000015")

    def test_barcode_with_volume_liters(self):
        """Test barcode with volume in liters"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_serial,
            quantity=1.5,
            uom=self.volume_uom_liter,
        )
        self.assertEqual(barcode, f"01{self.product_tracking_serial.barcode}3101000015")

    def test_barcode_with_high_precision(self):
        """Test barcode with high precision quantity"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot, quantity=1.234, uom=self.weight_uom_kg
        )
        self.assertEqual(barcode, f"01{self.product_tracking_lot.barcode}3102000124")

    def test_barcode_with_zero_quantity(self):
        """Test barcode with zero quantity should not include quantity in barcode"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=0
        )
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}")

    def test_barcode_with_negative_quantity(self):
        """Test barcode with negative quantity (should use absolute value)"""
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode(
                product_id=self.product_tracking_none, quantity=-5
            )

    def test_barcode_with_large_quantity(self):
        """Test barcode with large quantity"""
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=99999999
        )
        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}3099999999")
