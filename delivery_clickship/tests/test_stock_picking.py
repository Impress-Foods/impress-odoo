import logging
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..models.schema import Date, Money, Rate, RateResponse, RateStatus
from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestStockPicking(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_clickship_fields_exist(self):
        """Test that ClickShip fields exist on stock picking"""
        picking = self.make_picking()

        # Check that fields exist
        self.assertTrue(hasattr(picking, "clickship_tracking_url"))
        self.assertTrue(hasattr(picking, "clickship_shipment_id"))
        self.assertTrue(hasattr(picking, "clickship_service_id"))
        self.assertTrue(hasattr(picking, "clickship_rate_needed"))

    def test_compute_clickship_rate_needed_true(self):
        """Test that clickship_rate_needed is True when service_id is missing"""
        picking = self.make_picking()

        # Should be True when carrier is clickship and no service_id
        self.assertTrue(picking.clickship_rate_needed)

    def test_compute_clickship_rate_needed_false_with_service_id(self):
        """Test that clickship_rate_needed is False when service_id is present"""
        picking = self.make_picking()
        picking.clickship_service_id = "test_service_id"

        # Should be False when service_id is present
        self.assertFalse(picking.clickship_rate_needed)

    def test_compute_clickship_rate_needed_false_different_carrier(self):
        """Test that clickship_rate_needed is False for non-clickship carriers"""
        picking = self.make_picking()
        # Create a different carrier
        delivery_product = self.env["product.product"].create(
            {"name": "Other Delivery", "type": "service"}
        )
        other_carrier = self.env["delivery.carrier"].create(
            {
                "name": "Other Carrier",
                "delivery_type": "fixed",
                "product_id": delivery_product.id,
                "fixed_price": 10.0,
            }
        )
        picking.carrier_id = other_carrier

        # Should be False when carrier is not clickship
        self.assertFalse(picking.clickship_rate_needed)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_carrier.ClickShipCarrier.clickship_get_raw_rates"
    )
    def test_action_get_clickship_rates(self, mock_get_raw_rates):
        """Test getting ClickShip rates and opening wizard"""
        mock_rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2000", currency="CAD"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
            Rate(
                service_id="service_2",
                service_name="Service 2",
                carrier_name="Carrier 2",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2500", currency="CAD"),
                transit_time_days=2,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]
        mock_get_raw_rates.return_value = RateResponse(
            status=RateStatus(done=True),
            rates=mock_rates,
        )

        picking = self.make_picking()
        result = picking.action_get_clickship_rates()

        # Check that wizard action is returned
        self.assertEqual(result["res_model"], "wizard.clickship_rates")
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["target"], "new")
        self.assertEqual(result["view_mode"], "form")

        # Check context
        self.assertEqual(result["context"]["default_picking_id"], picking.id)
        self.assertIn("default_rate_ids", result["context"])

        # Check that rates were created
        rate_ids = result["context"]["default_rate_ids"]
        self.assertEqual(len(rate_ids), 2)

        rates = self.env["clickship.rate"].browse(rate_ids)
        self.assertEqual(len(rates), 2)

        rate_1 = rates.filtered(lambda r: r.service_id == "service_1")
        self.assertEqual(rate_1.service_name, "Service 1")
        self.assertEqual(rate_1.carrier_name, "Carrier 1")
        self.assertEqual(rate_1.total, 20.0)  # 2000 cents = 20.00
        self.assertEqual(rate_1.transit_time, 1)
        self.assertTrue(rate_1.transit_time_valid)

        rate_2 = rates.filtered(lambda r: r.service_id == "service_2")
        self.assertEqual(rate_2.service_name, "Service 2")
        self.assertEqual(rate_2.carrier_name, "Carrier 2")
        self.assertEqual(rate_2.total, 25.0)  # 2500 cents = 25.00
        self.assertEqual(rate_2.transit_time, 2)
        self.assertTrue(rate_2.transit_time_valid)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_carrier.ClickShipCarrier.clickship_get_raw_rates"
    )
    def test_action_get_clickship_rates_skip_unavailable_transit_time(
        self, mock_get_raw_rates
    ):
        """Test that rates with unavailable transit time are skipped"""
        mock_rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2000", currency="CAD"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
            Rate(
                service_id="service_2",
                service_name="Service 2",
                carrier_name="Carrier 2",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2500", currency="CAD"),
                transit_time_days=2,
                transit_time_not_available=True,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]
        mock_get_raw_rates.return_value = RateResponse(
            status=RateStatus(done=True),
            rates=mock_rates,
        )

        picking = self.make_picking()
        result = picking.action_get_clickship_rates()

        # Check that only one rate was created (the one with available transit time)
        rate_ids = result["context"]["default_rate_ids"]
        self.assertEqual(len(rate_ids), 1)

        rates = self.env["clickship.rate"].browse(rate_ids)
        self.assertEqual(rates.service_id, "service_1")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_carrier.ClickShipCarrier.clickship_get_raw_rates"
    )
    def test_action_get_clickship_rates_unknown_currency(self, mock_get_raw_rates):
        """Test handling of unknown currency"""
        mock_rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2000", currency="XYZ"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]
        mock_get_raw_rates.return_value = RateResponse(
            status=RateStatus(done=True),
            rates=mock_rates,
        )

        picking = self.make_picking()

        with self.assertRaises(ValidationError) as context:  # type: ignore
            picking.action_get_clickship_rates()

        self.assertIn("Could not find currency with name XYZ", str(context.exception))

    def test_clickship_parse_rates_valid_rates(self):
        """Test parsing valid ClickShip rates"""
        rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2000", currency="CAD"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
            Rate(
                service_id="service_2",
                service_name="Service 2",
                carrier_name="Carrier 2",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2500", currency="CAD"),
                transit_time_days=2,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]

        picking = self.make_picking()
        result = picking._clickship_parse_rates(rates)

        self.assertEqual(len(result), 2)

        # Check first rate
        rate_1 = result.filtered(lambda r: r.service_id == "service_1")
        self.assertEqual(rate_1.service_name, "Service 1")
        self.assertEqual(rate_1.carrier_name, "Carrier 1")
        self.assertEqual(rate_1.total, 20.0)  # 2000 cents = 20.00
        self.assertEqual(rate_1.transit_time, 1)
        self.assertTrue(rate_1.transit_time_valid)

        # Check second rate
        rate_2 = result.filtered(lambda r: r.service_id == "service_2")
        self.assertEqual(rate_2.service_name, "Service 2")
        self.assertEqual(rate_2.carrier_name, "Carrier 2")
        self.assertEqual(rate_2.total, 25.0)  # 2500 cents = 25.00
        self.assertEqual(rate_2.transit_time, 2)
        self.assertTrue(rate_2.transit_time_valid)

    def test_clickship_parse_rates_skip_unavailable_transit_time(self):
        """Test that rates with unavailable transit time are skipped during parsing"""
        rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2000", currency="CAD"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
            Rate(
                service_id="service_2",
                service_name="Service 2",
                carrier_name="Carrier 2",
                base=Money(value="1000", currency="CAD"),
                total=Money(value="2500", currency="CAD"),
                transit_time_days=2,
                transit_time_not_available=True,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]

        picking = self.make_picking()
        result = picking._clickship_parse_rates(rates)

        # Only one rate should be created (the one with available transit time)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.service_id, "service_1")

    def test_clickship_parse_rates_unknown_currency(self):
        """Test parsing rates with unknown currency raises error"""
        rates = [
            Rate(
                service_id="service_1",
                service_name="Service 1",
                carrier_name="Carrier 1",
                base=Money(value="1000", currency="XYZ"),
                total=Money(value="2000", currency="XYZ"),
                transit_time_days=1,
                transit_time_not_available=False,
                valid_until=Date(year=2025, month=7, day=15),
            ),
        ]

        picking = self.make_picking()

        with self.assertRaises(ValidationError) as context:  # type: ignore
            picking._clickship_parse_rates(rates)

        self.assertIn("Could not find currency with name XYZ", str(context.exception))

    def test_get_fields_stock_barcode(self):
        """Test that clickship_rate_needed is included in barcode fields"""
        picking = self.make_picking()
        fields = picking._get_fields_stock_barcode()

        self.assertIn("clickship_rate_needed", fields)

    def test_clickship_fields_not_copied(self):
        """Test that ClickShip fields are not copied when duplicating picking"""
        picking = self.make_picking()
        picking.write(
            {
                "clickship_tracking_url": "https://tracking.clickship.com/12345",
                "clickship_shipment_id": "shipment_12345",
                "clickship_service_id": "service_12345",
            }
        )

        # Copy the picking
        copied_picking = picking.copy()

        # ClickShip fields should not be copied
        self.assertFalse(copied_picking.clickship_tracking_url)
        self.assertFalse(copied_picking.clickship_shipment_id)
        self.assertFalse(copied_picking.clickship_service_id)

        # But other fields should be copied
        self.assertEqual(copied_picking.partner_id, picking.partner_id)
        self.assertEqual(copied_picking.carrier_id, picking.carrier_id)

    def test_clickship_rate_needed_dependency(self):
        """Test that clickship_rate_needed depends on clickship_service_id"""
        picking = self.make_picking()

        # Initially should be True (no service_id)
        self.assertTrue(picking.clickship_rate_needed)

        # Set service_id, should become False
        picking.clickship_service_id = "test_service"
        self.assertFalse(picking.clickship_rate_needed)

        # Clear service_id, should become True again
        picking.clickship_service_id = False
        self.assertTrue(picking.clickship_rate_needed)

    def test_multiple_pickings_rate_needed(self):
        """Test clickship_rate_needed computation for multiple pickings"""
        # Create multiple pickings
        picking1 = self.make_picking()
        picking2 = self.make_picking()

        # Set service_id on one picking
        picking1.clickship_service_id = "service_1"

        # Check computed values
        self.assertFalse(picking1.clickship_rate_needed)
        self.assertTrue(picking2.clickship_rate_needed)

    def test_clickship_fields_default_values(self):
        """Test that ClickShip fields have proper default values"""
        picking = self.make_picking()

        # All ClickShip fields should be False/empty by default
        self.assertFalse(picking.clickship_tracking_url)
        self.assertFalse(picking.clickship_shipment_id)
        self.assertFalse(picking.clickship_service_id)

        # clickship_rate_needed should be computed as True (no service_id)
        self.assertTrue(picking.clickship_rate_needed)
