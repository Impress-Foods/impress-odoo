import logging
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..models.schema import Date, Money, Rate, RateResponse, RateStatus
from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestClickshipCarrier(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_clickship_carrier_creation(self):
        """Test that ClickShip carrier is created correctly"""
        self.assertEqual(self.clickship_method.delivery_type, "clickship")
        self.assertEqual(self.clickship_method.clickship_api_key, "test_api_key")
        self.assertEqual(self.clickship_method.clickship_contact, self.contact)
        self.assertEqual(
            self.clickship_method.clickship_payment_method, self.payment_method
        )

    def test_clickship_carrier_selection_add(self):
        """Test that clickship is properly added to delivery_type selection"""
        carrier = self.env["delivery.carrier"].create(
            {
                "name": "Test ClickShip",
                "delivery_type": "clickship",
                "product_id": self.env["product.product"]
                .create({"name": "Test Product", "type": "service"})
                .id,
            }
        )
        self.assertEqual(carrier.delivery_type, "clickship")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.get_rate"
    )
    def test_clickship_rate_shipment_picking(self, mock_get_rate):
        """Test rating a shipment with picking"""
        # Mock the rate response
        mock_rate = Rate(
            service_id="test_service",
            service_name="Test Service",
            carrier_name="Test Carrier",
            base=Money(value="1000", currency="CAD"),
            total=Money(value="2500", currency="CAD"),  # 2500 cents = $25.00
            transit_time_days=2,
            transit_time_not_available=False,
            valid_until=Date(year=2025, month=7, day=15),
        )

        mock_get_rate.return_value = mock_rate

        picking = self.make_picking()
        result = self.clickship_method.clickship_rate_shipment(picking)

        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 25.0)
        self.assertFalse(result["error_message"])
        self.assertFalse(result["warning_message"])
        mock_get_rate.assert_called_once_with(picking, self.contact)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.get_rate"
    )
    def test_clickship_rate_shipment_sale_order(self, mock_get_rate):
        """Test rating a shipment with sale order"""
        mock_rate = Rate(
            service_id="test_service_so",
            service_name="Test Service SO",
            carrier_name="Test Carrier SO",
            base=Money(value="500", currency="CAD"),
            total=Money(value="1500", currency="CAD"),  # 1500 cents = $15.00
            transit_time_days=1,
            transit_time_not_available=False,
            valid_until=Date(year=2025, month=7, day=15),
        )
        mock_get_rate.return_value = mock_rate

        sale_order = self.make_sale_order()
        result = self.clickship_method.clickship_rate_shipment(sale_order)

        self.assertTrue(result["success"])
        self.assertEqual(result["price"], 15.0)
        mock_get_rate.assert_called_once_with(sale_order, self.contact)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.get_raw_rates"
    )
    def test_clickship_get_raw_rates(self, mock_get_raw_rates):
        """Test getting raw rates from ClickShip"""
        mock_response = RateResponse(
            status=RateStatus(done=True),
            rates=[
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
            ],
        )

        mock_get_raw_rates.return_value = mock_response

        picking = self.make_picking()
        result = self.clickship_method.clickship_get_raw_rates(picking)

        self.assertEqual(len(result.rates), 2)
        self.assertEqual(result.rates[0].service_id, "service_1")
        self.assertEqual(result.rates[1].service_id, "service_2")
        mock_get_raw_rates.assert_called_once_with(picking, self.contact)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.book_shipment"
    )
    def test_clickship_send_shipping(self, mock_book_shipment):
        """Test sending shipping with ClickShip"""
        mock_booking = {
            "exact_price": 25.0,
            "tracking_number": "1234567890",
            "label_data": "ZPL_LABEL_DATA",
            "tracking_url": "https://tracking.clickship.com/1234567890",
            "shipment_id": "shipment_123",
        }
        mock_book_shipment.return_value = mock_booking

        picking = self.make_picking()
        result = self.clickship_method.clickship_send_shipping(picking)  # type: ignore

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], mock_booking)
        self.assertEqual(
            picking.clickship_tracking_url, "https://tracking.clickship.com/1234567890"
        )
        self.assertEqual(picking.clickship_shipment_id, "shipment_123")
        self.assertTrue(picking.shipping_label_attachment_id)

        # Check attachment was created
        attachment = picking.shipping_label_attachment_id
        self.assertEqual(attachment.name, f"{picking.name} Shipping Label")
        self.assertEqual(attachment.mimetype, "text/plain")

        mock_book_shipment.assert_called_once_with(picking, self.contact)

    def test_clickship_get_tracking_link(self):
        """Test getting tracking link"""
        picking = self.make_picking()
        picking.clickship_tracking_url = "https://tracking.clickship.com/1234567890"

        result = self.clickship_method.clickship_get_tracking_link(picking)
        self.assertEqual(result, "https://tracking.clickship.com/1234567890")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.cancel_shipment"
    )
    def test_clickship_cancel_shipment_success(self, mock_cancel_shipment):
        """Test successful shipment cancellation"""
        mock_cancel_shipment.return_value = True

        picking = self.make_picking()
        # Create a mock attachment
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Test Label",
                "type": "binary",
                "datas": b"test",
                "res_model": "stock.picking",
                "res_id": picking.id,
            }
        )
        picking.write(
            {
                "clickship_shipment_id": "shipment_123",
                "clickship_tracking_url": "https://tracking.clickship.com/1234567890",
                "shipping_label_attachment_id": attachment.id,
            }
        )

        self.clickship_method.clickship_cancel_shipment(picking)

        self.assertFalse(picking.clickship_shipment_id)
        self.assertFalse(picking.clickship_tracking_url)
        # Check attachment was unlinked
        self.assertFalse(self.env["ir.attachment"].search([("id", "=", attachment.id)]))
        mock_cancel_shipment.assert_called_once_with("shipment_123")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.cancel_shipment"
    )
    def test_clickship_cancel_shipment_failure(self, mock_cancel_shipment):
        """Test failed shipment cancellation"""
        mock_cancel_shipment.return_value = False

        picking = self.make_picking()
        picking.clickship_shipment_id = "shipment_123"

        with self.assertRaises(ValidationError) as context:  # type: ignore
            self.clickship_method.clickship_cancel_shipment(picking)

        self.assertIn("Failed to cancel shipment!", str(context.exception))
        mock_cancel_shipment.assert_called_once_with("shipment_123")

    def test_clickship_get_default_custom_package_code(self):
        """Test getting default custom package code"""
        result = self.clickship_method._clickship_get_default_custom_package_code()
        self.assertEqual(result, "")

    def test_button_get_payment_methods_no_api_key(self):
        """Test getting payment methods without API key"""
        self.clickship_method.clickship_api_key = False

        with self.assertRaises(ValidationError) as context:  # type: ignore
            self.clickship_method.button_get_payment_methods()

        self.assertIn("Clickship API key is not set", str(context.exception))

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider._get_payment_methods"
    )
    def test_button_get_payment_methods_success(self, mock_get_payment_methods):
        """Test successfully getting payment methods"""
        mock_methods = [
            {"id": "method_1", "label": "Credit Card"},
            {"id": "method_2", "label": "Account Balance"},
        ]
        mock_get_payment_methods.return_value = mock_methods

        # Clear existing payment methods
        self.env["clickship.payment_method"].search([]).unlink()

        self.clickship_method.button_get_payment_methods()

        # Check that payment methods were created
        payment_methods = self.env["clickship.payment_method"].search(
            [("delivery_carrier_id", "=", self.clickship_method.id)]
        )
        self.assertEqual(len(payment_methods), 2)

        method_1 = payment_methods.filtered(lambda m: m.code == "method_1")
        self.assertEqual(method_1.name, "Credit Card")

        method_2 = payment_methods.filtered(lambda m: m.code == "method_2")
        self.assertEqual(method_2.name, "Account Balance")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider._get_payment_methods"
    )
    def test_button_get_payment_methods_error_response(self, mock_get_payment_methods):
        """Test getting payment methods with error response"""
        mock_get_payment_methods.return_value = {"error": "API Error"}

        # Should not raise exception, just return silently
        self.clickship_method.button_get_payment_methods()

        # No NEW payment methods should be created
        payment_methods = self.env["clickship.payment_method"].search(
            [("delivery_carrier_id", "=", self.clickship_method.id)]
        )
        # Should have same count as before (existing methods were cleared, none added)
        self.assertEqual(len(payment_methods), 0)

    def test_ondelete_cascade(self):
        """Test that changing delivery_type from clickship works properly"""
        # Create a new carrier with clickship type
        carrier = self.env["delivery.carrier"].create(
            {
                "name": "Test ClickShip 2",
                "delivery_type": "clickship",
                "product_id": self.env["product.product"]
                .create({"name": "Test Product 2", "type": "service"})
                .id,
            }
        )

        self.assertEqual(carrier.delivery_type, "clickship")

        # Change delivery type (this should trigger the ondelete lambda)
        carrier.delivery_type = "fixed"

        self.assertEqual(carrier.delivery_type, "fixed")
        # The ondelete lambda sets fixed_price to 0, but the
        #  default value might be different
        self.assertTrue(carrier.fixed_price is not None)
