import logging

from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


class TestRateModel(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_rate_model_creation(self):
        """Test creating clickship.rate records"""
        # Create a currency
        currency = self.env.ref("base.CAD")

        rate = self.env["clickship.rate"].create(
            {
                "carrier_name": "Test Carrier",
                "service_name": "Test Service",
                "service_id": "test_service_id",
                "transit_time": 2,
                "transit_time_valid": True,
                "total": 25.50,
                "currency_id": currency.id,
            }
        )

        self.assertEqual(rate.carrier_name, "Test Carrier")
        self.assertEqual(rate.service_name, "Test Service")
        self.assertEqual(rate.service_id, "test_service_id")
        self.assertEqual(rate.transit_time, 2)
        self.assertTrue(rate.transit_time_valid)
        self.assertEqual(rate.total, 25.50)
        self.assertEqual(rate.currency_id, currency)

    def test_rate_model_rec_name(self):
        """Test that rate model uses carrier_name as record name"""
        currency = self.env.ref("base.CAD")

        rate = self.env["clickship.rate"].create(
            {
                "carrier_name": "Test Carrier Name",
                "service_name": "Test Service",
                "service_id": "test_service_id",
                "transit_time": 1,
                "transit_time_valid": True,
                "total": 15.00,
                "currency_id": currency.id,
            }
        )

        self.assertEqual(rate.display_name, "Test Carrier Name")

    def test_rate_model_ordering(self):
        """Test that rates are ordered by total amount ascending"""
        currency = self.env.ref("base.CAD")

        # Create rates with different totals
        rate1 = self.env["clickship.rate"].create(
            {
                "carrier_name": "Expensive Carrier",
                "service_name": "Expensive Service",
                "service_id": "expensive_service",
                "total": 50.00,
                "currency_id": currency.id,
            }
        )

        rate2 = self.env["clickship.rate"].create(
            {
                "carrier_name": "Cheap Carrier",
                "service_name": "Cheap Service",
                "service_id": "cheap_service",
                "total": 10.00,
                "currency_id": currency.id,
            }
        )

        rate3 = self.env["clickship.rate"].create(
            {
                "carrier_name": "Medium Carrier",
                "service_name": "Medium Service",
                "service_id": "medium_service",
                "total": 25.00,
                "currency_id": currency.id,
            }
        )

        # Search all rates and verify ordering
        rates = self.env["clickship.rate"].search(
            [("id", "in", [rate1.id, rate2.id, rate3.id])]
        )

        # Should be ordered by total ascending
        self.assertEqual(rates[0].id, rate2.id)  # Cheapest first
        self.assertEqual(rates[1].id, rate3.id)  # Medium second
        self.assertEqual(rates[2].id, rate1.id)  # Most expensive last

    def test_rate_model_wizard_relationship(self):
        """Test the relationship between rate and wizard"""
        currency = self.env.ref("base.CAD")

        # Create a wizard
        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": self.make_picking().id,
            }
        )

        # Create rates linked to the wizard
        rate1 = self.env["clickship.rate"].create(
            {
                "carrier_name": "Carrier 1",
                "service_name": "Service 1",
                "service_id": "service_1",
                "total": 15.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            }
        )

        rate2 = self.env["clickship.rate"].create(
            {
                "carrier_name": "Carrier 2",
                "service_name": "Service 2",
                "service_id": "service_2",
                "total": 25.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            }
        )

        # Test relationships
        self.assertEqual(rate1.wizard_id, wizard)
        self.assertEqual(rate2.wizard_id, wizard)
        self.assertIn(rate1, wizard.rate_ids)
        self.assertIn(rate2, wizard.rate_ids)

    def test_rate_model_fields_optional(self):
        """Test that optional fields can be empty"""
        currency = self.env.ref("base.CAD")

        # Create rate with minimal required fields
        rate = self.env["clickship.rate"].create(
            {
                "service_id": "test_service_id",
                "total": 20.00,
                "currency_id": currency.id,
            }
        )

        # Optional fields should be empty/false
        self.assertFalse(rate.carrier_name)
        self.assertFalse(rate.service_name)
        self.assertFalse(rate.transit_time)
        self.assertFalse(rate.transit_time_valid)
        self.assertFalse(rate.wizard_id)

    def test_rate_model_transient(self):
        """Test that rate model is transient"""
        # Check that the model is transient
        self.assertTrue(self.env["clickship.rate"]._transient)

    def test_rate_model_currency_relationship(self):
        """Test the Many2one relationship with currency"""
        currency_cad = self.env.ref("base.CAD")
        currency_usd = self.env.ref("base.USD")

        rate1 = self.env["clickship.rate"].create(
            {
                "carrier_name": "CAD Carrier",
                "service_id": "cad_service",
                "total": 25.00,
                "currency_id": currency_cad.id,
            }
        )

        rate2 = self.env["clickship.rate"].create(
            {
                "carrier_name": "USD Carrier",
                "service_id": "usd_service",
                "total": 20.00,
                "currency_id": currency_usd.id,
            }
        )

        self.assertEqual(rate1.currency_id, currency_cad)
        self.assertEqual(rate2.currency_id, currency_usd)
        self.assertEqual(rate1.currency_id.name, "CAD")
        self.assertEqual(rate2.currency_id.name, "USD")

    def test_rate_model_monetary_field(self):
        """Test that total field is monetary and works with currency"""
        currency = self.env.ref("base.CAD")

        rate = self.env["clickship.rate"].create(
            {
                "carrier_name": "Test Carrier",
                "service_id": "test_service",
                "total": 123.45,
                "currency_id": currency.id,
            }
        )

        # The total should be stored as provided
        self.assertEqual(rate.total, 123.45)
        # And the currency should be linked
        self.assertEqual(rate.currency_id, currency)

    def test_rate_model_multiple_rates_same_wizard(self):
        """Test creating multiple rates for the same wizard"""
        currency = self.env.ref("base.CAD")
        picking = self.make_picking()

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        # Create multiple rates for the same wizard
        rates_data = [
            {
                "carrier_name": "Carrier A",
                "service_name": "Service A",
                "service_id": "service_a",
                "total": 15.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            },
            {
                "carrier_name": "Carrier B",
                "service_name": "Service B",
                "service_id": "service_b",
                "total": 25.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            },
            {
                "carrier_name": "Carrier C",
                "service_name": "Service C",
                "service_id": "service_c",
                "total": 35.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            },
        ]

        rates = self.env["clickship.rate"].create(rates_data)

        # All rates should be created
        self.assertEqual(len(rates), 3)

        # All rates should be linked to the wizard
        for rate in rates:
            self.assertEqual(rate.wizard_id, wizard)

        # Wizard should have all rates
        self.assertEqual(len(wizard.rate_ids), 3)

        # Rates should be ordered by total (ascending)
        ordered_rates = wizard.rate_ids.sorted("total")
        self.assertEqual(ordered_rates[0].service_id, "service_a")
        self.assertEqual(ordered_rates[1].service_id, "service_b")
        self.assertEqual(ordered_rates[2].service_id, "service_c")
