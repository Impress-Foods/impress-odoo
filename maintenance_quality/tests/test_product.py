import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestProductProduct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        product_model = cls.env["product.product"]
        quality_point_model = cls.env["quality.point"]
        product_category_model = cls.env["product.category"]

        cls.category = product_category_model.create(
            {
                "name": "Test Category",
            }
        )

        cls.product = product_model.create(
            {
                "name": "Test Product",
                "categ_id": cls.category.id,
            }
        )

        cls.quality_point_product = quality_point_model.create(
            {
                "name": "Test Quality Point Product",
                "control_point_type": "stock",
                "product_ids": [(4, cls.product.id)],
            }
        )

        cls.quality_point_categ = quality_point_model.create(
            {
                "name": "Test Quality Point Category",
                "control_point_type": "stock",
                "product_category_ids": [(4, cls.category.id)],
            }
        )

        cls.quality_point_maintenance = quality_point_model.create(
            {
                "name": "Test Quality Point Maintenance",
                "control_point_type": "maintenance",
            }
        )

    def test_product_number_of_checks(self):
        self.assertEqual(self.product.quality_control_point_qty, 2)
