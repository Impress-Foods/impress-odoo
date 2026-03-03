from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSingleUsePerCustomer(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create(
            {"name": "Partner A", "email": "a@example.com"}
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "Partner B", "email": "b@example.com"}
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "list_price": 100.0,
            }
        )

        # Create a discount product for the loyalty program
        cls.discount_product = cls.env["product.product"].create(
            {
                "name": "Discount Product",
                "type": "service",
                "list_price": 0.0,
            }
        )

        cls.program = cls.env["loyalty.program"].create(
            {
                "name": "Promo 10%",
                "program_type": "promo_code",
                "applies_on": "current",
                "trigger": "with_code",
                "limit_usage_per_customer": True,
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "mode": "with_code",
                            "code": "PROMO10",
                        },
                    )
                ],
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount": 10,
                            "discount_mode": "percent",
                            "discount_applicability": "order",
                            "discount_line_product_id": cls.discount_product.id,
                        },
                    )
                ],
            }
        )

    def test_single_use_per_customer(self):
        # 1. Partner A uses the promo code
        order1 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        # Apply the code
        result = order1._try_apply_code("PROMO10")
        self.assertNotIn(
            "error", result, "Promo code should be applicable for the first time"
        )

        # In Odoo 17, _try_apply_code returns the claimable rewards.
        #   We need to apply one.
        for coupon, rewards in result.items():
            order1._apply_program_reward(rewards[0], coupon)

        self.assertTrue(
            order1.order_line.filtered("is_reward_line"), "Reward line should be added"
        )

        # Confirm the order
        order1.action_confirm()

        # 2. Partner A tries to use it again on a new order
        order2 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order2._try_apply_code("PROMO10")
        self.assertIn(
            "error", result, "Promo code should be blocked for the same partner"
        )
        self.assertEqual(
            result["error"], "This code has already been used by this customer."
        )

        # 3. Partner B uses the same code (should work)
        order3 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_b.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order3._try_apply_code("PROMO10")
        self.assertNotIn(
            "error", result, "Promo code should be applicable for a different partner"
        )

    def test_guest_email_matching(self):
        # 1. Partner A (with email a@example.com) uses the code and confirms
        order1 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order1._try_apply_code("PROMO10")
        for coupon, rewards in result.items():
            order1._apply_program_reward(rewards[0], coupon)
        order1.action_confirm()

        # 2. A guest (different partner record but same email) tries to use it
        guest_partner = self.env["res.partner"].create(
            {
                "name": "Guest A",
                "email": "a@example.com",  # Same email as Partner A
            }
        )
        order2 = self.env["sale.order"].create(
            {
                "partner_id": guest_partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order2._try_apply_code("PROMO10")
        self.assertIn("error", result, "Promo code should be blocked by email matching")

    def test_shipping_email_matching(self):
        # 1. Partner A (a@example.com) sends a gift to Friend C (c@example.com)
        friend_c = self.env["res.partner"].create(
            {"name": "Friend C", "email": "c@example.com"}
        )
        order1 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "partner_shipping_id": friend_c.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order1._try_apply_code("PROMO10")
        for coupon, rewards in result.items():
            order1._apply_program_reward(rewards[0], coupon)
        order1.action_confirm()

        # 2. Friend C tries to use the code for themselves
        order2 = self.env["sale.order"].create(
            {
                "partner_id": friend_c.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        result = order2._try_apply_code("PROMO10")
        self.assertIn(
            "error",
            result,
            "Promo code should be blocked because the email was already"
            " used as a shipping address",
        )
