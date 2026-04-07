from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestProduct(TransactionCase):
    def test_compute_misc_test_count_target_and_related(self) -> None:
        product = self.env["product.template"].create(
            {
                "name": "Product 1",
                "type": "consu",
            }
        )
        self.env["misc.test"].create(
            {
                "product_id": product.id,
                "affected_product_ids": [Command.link(product.id)],
            }
        )

        self.assertEqual(product.misc_test_count, 1)

    def test_compute_misc_test_count_related(self) -> None:
        product = self.env["product.template"].create(
            {
                "name": "Product 1",
                "type": "consu",
            }
        )
        self.env["misc.test"].create(
            {
                "affected_product_ids": [Command.link(product.id)],
            }
        )

        self.assertEqual(product.misc_test_count, 1)

    def test_compute_misc_test_count_target(self) -> None:
        product = self.env["product.template"].create(
            {
                "name": "Product 1",
                "type": "consu",
            }
        )
        self.env["misc.test"].create(
            {
                "product_id": product.id,
            }
        )

        self.assertEqual(product.misc_test_count, 1)
