import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestProductProduct(TransactionCase):
    def setUp(self):
        super().setUp()

        product_model = self.env["product.product"]
        quality_point_model = self.env["quality.point"]
        product_category_model = self.env["product.category"]

        self.category = product_category_model.create(
            {
                "name": "Test Category",
            }
        )

        self.product = product_model.create(
            {
                "name": "Test Product",
                "categ_id": self.category.id,
            }
        )

        self.quality_point_product = quality_point_model.create(
            {
                "name": "Test Quality Point Product",
                "control_point_type": "stock",
                "product_ids": [(4, self.product.id)],
            }
        )

        self.quality_point_categ = quality_point_model.create(
            {
                "name": "Test Quality Point Category",
                "control_point_type": "stock",
                "product_category_ids": [(4, self.category.id)],
            }
        )

        self.quality_point_maintenance = quality_point_model.create(
            {
                "name": "Test Quality Point Maintenance",
                "control_point_type": "maintenance",
            }
        )

    def test_product_number_of_checks(self):
        self.assertEqual(self.product.quality_control_point_qty, 2)
