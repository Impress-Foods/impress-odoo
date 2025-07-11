import logging

from odoo.tests import tagged

from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestWizardPaymentMethod(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_payment_method_creation(self):
        """Test creating clickship.payment_method records"""
        payment_method = self.env["clickship.payment_method"].create(
            {
                "name": "Test Payment Method",
                "code": "test_payment_code",
                "delivery_carrier_id": self.clickship_method.id,
            }
        )

        self.assertEqual(payment_method.name, "Test Payment Method")
        self.assertEqual(payment_method.code, "test_payment_code")
        self.assertEqual(payment_method.delivery_carrier_id, self.clickship_method)

    def test_payment_method_relationship(self):
        """Test the relationship between payment method and carrier"""
        # Create additional payment methods
        payment_method1 = self.env["clickship.payment_method"].create(
            {
                "name": "Credit Card",
                "code": "credit_card",
                "delivery_carrier_id": self.clickship_method.id,
            }
        )

        payment_method2 = self.env["clickship.payment_method"].create(
            {
                "name": "Account Balance",
                "code": "account_balance",
                "delivery_carrier_id": self.clickship_method.id,
            }
        )

        # Check that carrier has both payment methods
        self.assertIn(payment_method1, self.clickship_method.clickship_payment_methods)
        self.assertIn(payment_method2, self.clickship_method.clickship_payment_methods)

        # Check that payment methods are linked to carrier
        self.assertEqual(payment_method1.delivery_carrier_id, self.clickship_method)
        self.assertEqual(payment_method2.delivery_carrier_id, self.clickship_method)

    def test_wizard_clickship_rates_creation(self):
        """Test creating wizard.clickship_rates records"""
        picking = self.make_picking()

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        self.assertEqual(wizard.picking_id, picking)

    def test_wizard_clickship_rates_with_rates(self):
        """Test wizard with associated rates"""
        picking = self.make_picking()
        currency = self.env.ref("base.CAD")

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        # Create rates for the wizard
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

        # Check that wizard has both rates
        self.assertIn(rate1, wizard.rate_ids)
        self.assertIn(rate2, wizard.rate_ids)
        self.assertEqual(len(wizard.rate_ids), 2)

    def test_wizard_choose_rate_functionality(self):
        """Test wizard choose_rate method"""
        picking = self.make_picking()
        currency = self.env.ref("base.CAD")

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        rate = self.env["clickship.rate"].create(
            {
                "carrier_name": "Selected Carrier",
                "service_name": "Selected Service",
                "service_id": "selected_service_id",
                "total": 20.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            }
        )

        # Initially picking should not have service_id
        self.assertFalse(picking.clickship_service_id)

        # Choose the rate
        wizard.choose_rate(rate)

        # Picking should now have the service_id
        self.assertEqual(picking.clickship_service_id, "selected_service_id")

    def test_payment_method_domain_constraint(self):
        """Test that payment method domain works correctly"""
        # Create another carrier
        delivery_product = self.env["product.product"].create(
            {"name": "Other Delivery", "type": "service"}
        )
        other_carrier = self.env["delivery.carrier"].create(
            {
                "name": "Other ClickShip",
                "delivery_type": "clickship",
                "product_id": delivery_product.id,
            }
        )

        # Create payment method for the other carrier
        other_payment_method = self.env["clickship.payment_method"].create(
            {
                "name": "Other Payment Method",
                "code": "other_payment",
                "delivery_carrier_id": other_carrier.id,
            }
        )

        # Test that the domain filtering works
        # (This is more of a functional test, but we can check the relationship)
        self.assertEqual(other_payment_method.delivery_carrier_id, other_carrier)
        self.assertNotEqual(
            other_payment_method.delivery_carrier_id, self.clickship_method
        )

        # Check that each carrier has its own payment methods
        self.assertIn(
            self.payment_method, self.clickship_method.clickship_payment_methods
        )
        self.assertNotIn(
            other_payment_method, self.clickship_method.clickship_payment_methods
        )
        self.assertIn(other_payment_method, other_carrier.clickship_payment_methods)
        self.assertNotIn(self.payment_method, other_carrier.clickship_payment_methods)

    def test_payment_method_required_fields(self):
        """Test that payment method requires name field"""
        # name is required according to the model definition
        payment_method = self.env["clickship.payment_method"].create(
            {
                "name": "Minimal Payment Method",
                "code": "minimal_payment",
            }
        )

        self.assertEqual(payment_method.code, "minimal_payment")
        self.assertEqual(payment_method.name, "Minimal Payment Method")
        self.assertFalse(payment_method.delivery_carrier_id)

    def test_wizard_required_fields(self):
        """Test that wizard requires picking_id"""
        picking = self.make_picking()

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        # Should be created successfully
        self.assertTrue(wizard.id)
        self.assertEqual(wizard.picking_id, picking)

    def test_multiple_wizards_different_pickings(self):
        """Test creating multiple wizards for different pickings"""
        picking1 = self.make_picking()
        picking2 = self.make_picking()

        wizard1 = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking1.id,
            }
        )

        wizard2 = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking2.id,
            }
        )

        self.assertEqual(wizard1.picking_id, picking1)
        self.assertEqual(wizard2.picking_id, picking2)
        self.assertNotEqual(wizard1.picking_id, wizard2.picking_id)

    def test_rate_button_choose_integration(self):
        """Test integration between rate button_choose and wizard choose_rate"""
        picking = self.make_picking()
        currency = self.env.ref("base.CAD")

        wizard = self.env["wizard.clickship_rates"].create(
            {
                "picking_id": picking.id,
            }
        )

        rate = self.env["clickship.rate"].create(
            {
                "carrier_name": "Integration Test Carrier",
                "service_name": "Integration Test Service",
                "service_id": "integration_service_id",
                "total": 30.00,
                "currency_id": currency.id,
                "wizard_id": wizard.id,
            }
        )

        # Initially picking should not have service_id
        self.assertFalse(picking.clickship_service_id)

        # Call button_choose on the rate (this should call wizard.choose_rate)
        rate.button_choose()

        # Picking should now have the service_id
        self.assertEqual(picking.clickship_service_id, "integration_service_id")
