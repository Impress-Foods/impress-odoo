import json
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import requests
from freezegun import freeze_time

from odoo.exceptions import ValidationError

from ..models.schema import (
    Address,
    Box,
    Cuboid,
    Date,
    Destination,
    Money,
    Origin,
    Package,
    PhoneNumber,
    Rate,
    RateResponse,
    RateStatus,
    ShippingDetails,
    Weight,
)
from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


class TestClickshipRequest(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_clickship_provider_initialization(self):
        """Test ClickshipProvider initialization"""
        provider = self.sr
        self.assertEqual(provider.token, "test_token")
        self.assertEqual(
            provider.url, "https://customer-external-api.ssd-test.freightcom.com"
        )
        self.assertIsNotNone(provider.session)

    def test_clickship_provider_prod_url(self):
        """Test ClickshipProvider with production URL"""
        from ..models.clickship_request import ClickshipProvider

        provider = ClickshipProvider(
            debug_logger=lambda msg, name: None,
            prod_environment=True,
            token="test_token",
        )
        self.assertEqual(provider.url, "https://external-api.freightcom.com")

    def test_make_address_partner(self):
        """Test creating address from partner"""
        expected_address = Address(
            address_line_1=self.partner.street,
            address_line_2=self.partner.street2,
            city=self.partner.city,
            region=self.partner.state_id.code,
            country=self.partner.country_id.code,
            postal_code=self.partner.zip,
        )

        address = self.sr._make_address(self.partner)
        self.assertEqual(address, expected_address)

    def test_make_address_company(self):
        """Test creating address from company"""
        company = self.env.company
        # Ensure company has required address fields
        company.write(
            {
                "street": "123 Company St",
                "street2": "Suite 100",
                "city": "Company City",
                "state_id": self.env["res.country.state"]
                .search([("code", "=", "QC")], limit=1)
                .id,
                "country_id": self.env["res.country"]
                .search([("code", "=", "CA")], limit=1)
                .id,
                "zip": "H1A1A1",
            }
        )

        expected_address = Address(
            address_line_1=company.street,
            address_line_2=company.street2,
            city=company.city,
            region=company.state_id.code,
            country=company.country_id.code,
            postal_code=company.zip,
        )

        address = self.sr._make_address(company)
        self.assertEqual(address, expected_address)

    def test_make_address_hr_employee(self):
        """Test creating address from HR employee"""
        # Ensure the employee's company has required address fields
        self.contact.company_id.write(
            {
                "street": "456 Employee Company St",
                "street2": "Floor 2",
                "city": "Employee City",
                "state_id": self.env["res.country.state"]
                .search([("code", "=", "QC")], limit=1)
                .id,
                "country_id": self.env["res.country"]
                .search([("code", "=", "CA")], limit=1)
                .id,
                "zip": "H2B2B2",
            }
        )

        expected_address = Address(
            address_line_1=self.contact.company_id.street,
            address_line_2=self.contact.company_id.street2,
            city=self.contact.company_id.city,
            region=self.contact.company_id.state_id.code,
            country=self.contact.company_id.country_id.code,
            postal_code=self.contact.company_id.zip,
        )

        address = self.sr._make_address(self.contact)
        self.assertEqual(address, expected_address)

    def test_make_address_invalid_partner(self):
        """Test creating address with invalid partner"""
        with self.assertRaises(ValidationError) as context:  # type: ignore
            self.sr._make_address(None)  # type: ignore

        self.assertIn("Could not make address for", str(context.exception))

    @freeze_time(datetime(2025, 7, 15, 10, 30, 0, tzinfo=ZoneInfo("America/Montreal")))
    def test_make_current_date(self):
        """Test creating current date"""
        expected_date = Date(year=2025, month=7, day=15)
        current_date = self.sr._make_current_date()
        self.assertEqual(current_date, expected_date)

    def test_make_origin(self):
        """Test creating origin from order and contact"""
        picking = self.make_picking()
        expected_origin = Origin(
            name=picking.company_id.name,
            address=self.sr._make_address(picking.company_id),
            phone_number=PhoneNumber(number=picking.company_id.phone),
            email_addresses=[picking.company_id.email],
            contact_name=self.contact.name,
        )

        origin = self.sr._make_origin(picking, self.contact)
        self.assertEqual(origin, expected_origin)

    def test_make_destination(self):
        """Test creating destination from order"""
        picking = self.make_picking()
        expected_destination = Destination(
            name=self.partner.name,
            address=self.sr._make_address(self.partner),
            residential=True,
            phone_number=PhoneNumber(number=self.partner.phone),
            email_addresses=[self.partner.email],
            contact_name=self.partner.name,
        )

        destination = self.sr._make_destination(picking)
        self.assertEqual(destination, expected_destination)

    def test_make_package_with_package(self):
        """Test creating package from stock.quant.package"""
        picking = self.make_picking()
        package = picking.package_ids[0]

        expected_package = Package(
            measurements=Box(
                weight=Weight(unit="kg", value=package.shipping_weight or 4.55),
                cuboid=Cuboid(
                    unit="mm",
                    l=package.package_type_id.packaging_length or 254,
                    w=package.package_type_id.width or 254,
                    h=package.package_type_id.height or 254,
                ),
            ),
            description=package.package_type_id.name or "Box",
        )

        package_data = self.sr._make_package(package)
        self.assertEqual(package_data, expected_package)

    def test_make_package_no_package(self):
        """Test creating default package when no package provided"""
        expected_package = Package(
            measurements=Box(
                weight=Weight(unit="kg", value=4.55),
                cuboid=Cuboid(unit="mm", l=254, w=254, h=254),
            ),
            description="Box",
        )

        package_data = self.sr._make_package(None)
        self.assertEqual(package_data, expected_package)

    def test_get_phone_number_partner(self):
        """Test getting phone number from partner"""
        phone = self.sr._get_phone_number(self.partner)
        self.assertEqual(phone, self.partner.phone)

    def test_get_phone_number_employee(self):
        """Test getting phone number from HR employee"""
        phone = self.sr._get_phone_number(self.contact)
        self.assertEqual(phone, self.contact.work_phone)

    def test_get_phone_number_invalid(self):
        """Test getting phone number from invalid object"""
        phone = self.sr._get_phone_number(None)  # type: ignore
        self.assertEqual(phone, "")

    @freeze_time(datetime(2025, 7, 15, 10, 30, 0, tzinfo=ZoneInfo("America/Montreal")))
    def test_make_shipping_details_picking(self):
        """Test creating shipping details from picking"""
        picking = self.make_picking()

        expected_details = ShippingDetails(
            origin=self.sr._make_origin(picking, self.contact),
            destination=self.sr._make_destination(picking),
            expected_ship_date=self.sr._make_current_date(),
            packaging_type="package",
            packaging_properties={
                "packages": [self.sr._make_package(pkg) for pkg in picking.package_ids]  # type: ignore
            },
        )

        details = self.sr._make_shipping_details(picking, self.contact)
        self.assertEqual(details.origin, expected_details.origin)
        self.assertEqual(details.destination, expected_details.destination)
        self.assertEqual(
            details.expected_ship_date, expected_details.expected_ship_date
        )
        self.assertEqual(details.packaging_type, expected_details.packaging_type)

    @freeze_time(datetime(2025, 7, 15, 10, 30, 0, tzinfo=ZoneInfo("America/Montreal")))
    def test_make_shipping_details_sale_order(self):
        """Test creating shipping details from sale order"""
        sale_order = self.make_sale_order()

        details = self.sr._make_shipping_details(sale_order, self.contact)

        # Should create default package when no packages exist
        self.assertEqual(len(details.packaging_properties.packages), 1)  # type: ignore
        self.assertEqual(
            details.packaging_properties.packages[0],  # type: ignore
            self.sr._make_package(None),
        )

    def test_make_shipment_request(self):
        """Test creating shipment request"""
        picking = self.make_picking()
        picking.clickship_service_id = "test_service_id"
        picking.origin = "SO001"

        request = self.sr._make_shipment_request(picking, self.contact)

        self.assertEqual(request.unique_id, "SO001")
        self.assertEqual(request.service_id, "test_service_id")
        self.assertEqual(request.payment_method_id, self.payment_method.code)
        self.assertIsNotNone(request.details)
        self.assertIsNotNone(request.pickup_details)

    def test_make_shipment_request_no_origin(self):
        """Test creating shipment request with no origin"""
        picking = self.make_picking()
        picking.clickship_service_id = "test_service_id"

        request = self.sr._make_shipment_request(picking, self.contact)

        self.assertEqual(request.unique_id, picking.name)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.requests.Session.get"
    )
    def test_make_api_request_get_success(self, mock_get):
        """Test successful GET API request"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": true}'
        mock_get.return_value = mock_response

        result = self.sr._make_api_request("test-endpoint", "GET")

        self.assertEqual(result, {"success": True})
        mock_get.assert_called_once()

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.requests.Session.post"
    )
    def test_make_api_request_post_success(self, mock_post):
        """Test successful POST API request"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "12345"}
        mock_response.text = '{"id": "12345"}'
        mock_post.return_value = mock_response

        payload = {"test": "data"}
        result = self.sr._make_api_request("test-endpoint", "POST", payload)

        self.assertEqual(result, {"id": "12345"})
        mock_post.assert_called_once()

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.requests.Session.delete"
    )
    def test_make_api_request_delete_success(self, mock_delete):
        """Test successful DELETE API request"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"deleted": True}
        mock_response.text = '{"deleted": true}'
        mock_delete.return_value = mock_response

        result = self.sr._make_api_request("test-endpoint", "DELETE")

        self.assertEqual(result, {"deleted": True})
        mock_delete.assert_called_once()

    def test_make_api_request_unsupported_method(self):
        """Test API request with unsupported method"""
        result = self.sr._make_api_request("test-endpoint", "PATCH")

        self.assertEqual(result, {"errors": {"method": "Unsupported method: PATCH"}})

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.requests.Session.get"
    )
    def test_make_api_request_connection_error(self, mock_get):
        """Test API request with connection error"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = self.sr._make_api_request("test-endpoint", "GET")

        self.assertIn("errors", result)
        self.assertIn("timeout", result["errors"])

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.requests.Session.get"
    )
    def test_make_api_request_json_decode_error(self, mock_get):
        """Test API request with JSON decode error"""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = self.sr._make_api_request("test-endpoint", "GET")

        self.assertIn("errors", result)
        self.assertIn("JSONDecodeError", result["errors"])

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider._make_api_request"
    )
    def test_post_request_rate(self, mock_api_request):
        """Test posting rate request"""
        mock_api_request.return_value = {"request_id": "rate_12345"}

        from ..models.schema import RateRequestData, ShippingDetails

        data = RateRequestData(
            details=ShippingDetails(
                origin=self.sr._make_origin(self.make_picking(), self.contact),
                destination=self.sr._make_destination(self.make_picking()),
                expected_ship_date=self.sr._make_current_date(),
                packaging_type="package",
                packaging_properties={"packages": [self.sr._make_package(None)]},  # type: ignore
            )
        )

        result = self.sr._post_request_rate(data)

        self.assertEqual(result, "rate_12345")
        mock_api_request.assert_called_once_with("rate", "POST", payload=data)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider._make_api_request"
    )
    def test_get_requested_rate(self, mock_api_request):
        """Test getting requested rate"""
        mock_response = {
            "status": {"done": True},
            "rates": [
                {
                    "service_id": "service_1",
                    "service_name": "Service 1",
                    "carrier_name": "Carrier 1",
                    "valid_until": {"year": 2025, "month": 7, "day": 15},
                    "total": {"value": "2500", "currency": "CAD"},
                    "base": {"value": "2000", "currency": "CAD"},
                    "surcharges": [],
                    "taxes": [],
                    "transit_time_days": 2,
                    "transit_time_not_available": False,
                }
            ],
        }
        mock_api_request.return_value = mock_response

        result = self.sr._get_requested_rate("rate_12345")

        self.assertIsInstance(result, RateResponse)
        self.assertTrue(result.status.done)
        self.assertEqual(len(result.rates), 1)
        mock_api_request.assert_called_once_with("rate/rate_12345", "GET")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider._make_api_request"
    )
    @patch("time.sleep")
    def test_get_raw_rates(self, mock_sleep, mock_api_request):
        """Test getting raw rates with polling"""
        # Mock the rate request post
        mock_api_request.side_effect = [
            {"request_id": "rate_12345"},  # First call to post rate
            {  # Second call to get rate (not done)
                "status": {"done": False},
                "rates": [],
            },
            {  # Third call to get rate (done)
                "status": {"done": True},
                "rates": [
                    {
                        "service_id": "service_1",
                        "service_name": "Service 1",
                        "carrier_name": "Carrier 1",
                        "valid_until": {"year": 2025, "month": 7, "day": 15},
                        "total": {"value": "2500", "currency": "CAD"},
                        "base": {"value": "2000", "currency": "CAD"},
                        "surcharges": [],
                        "taxes": [],
                        "transit_time_days": 2,
                        "transit_time_not_available": False,
                    }
                ],
            },
        ]

        picking = self.make_picking()
        result = self.sr.get_raw_rates(picking, self.contact)

        self.assertIsInstance(result, RateResponse)
        self.assertTrue(result.status.done)
        self.assertEqual(len(result.rates), 1)

        # Should have called API 3 times (post, get not done, get done)
        self.assertEqual(mock_api_request.call_count, 3)

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.get_raw_rates"
    )
    def test_get_rate_with_service_id(self, mock_get_raw_rates):
        """Test getting rate with specific service ID"""
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
        picking.clickship_service_id = "service_2"

        result = self.sr.get_rate(picking, self.contact)

        self.assertEqual(result.service_id, "service_2")
        self.assertEqual(result.service_name, "Service 2")

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.get_raw_rates"
    )
    def test_get_rate_no_service_id(self, mock_get_raw_rates):
        """Test getting rate without specific service ID (returns last rate)"""
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

        result = self.sr.get_rate(picking, self.contact)

        # Should return the last rate (service_2)
        self.assertEqual(result.service_id, "service_2")

    @patch("odoo.addons.delivery_clickship.models.clickship_request.urlopen")
    def test_fetch_label_data(self, mock_urlopen):
        """Test fetching label data from URL"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"ZPL_LABEL_DATA"
        mock_urlopen.return_value = mock_response

        result = self.sr._fetch_label_data("https://example.com/label.zpl")

        self.assertEqual(result, "ZPL_LABEL_DATA")
        mock_urlopen.assert_called_once_with(
            "https://example.com/label.zpl", timeout=30
        )
