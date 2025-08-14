from odoo.addons.impress_deposit.tests.test_common import TestCommon


class TestSaleOrder(TestCommon):
    def test_website_order(self):
        so = self.so_model.create(
            {
                "partner_id": self.partner_wo_deposit.id,
                # SO created with a website ID to simulate an ecom order
                "website_id": 1,
                "order_line": [
                    (
                        0,
                        0,
                        {"product_id": self.product_w_deposit.id, "product_uom_qty": 1},
                    )
                ],
            }
        )

        # Not confirming the SO since the deposit should be added
        # in the quotation stage (e-com cart)

        # Forcing the compute method to run
        _ = so.deposit_value

        deposit_line = so.order_line.filtered(lambda x: x.is_deposit_line)
        self.assertEqual(len(deposit_line), 1, "Deposit line not created")

        self.assertFalse(deposit_line._show_in_cart(), "Deposit line shown in cart")
        self.assertEqual(deposit_line.product_uom_qty, 1, "Incorrect deposit quantity")
