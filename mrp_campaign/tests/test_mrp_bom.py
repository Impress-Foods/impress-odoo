from odoo.exceptions import ValidationError

from .test_common import CampaignCase


class TestMrpBom(CampaignCase):
    def test_get_factor_to_product_no_line_for_product(self):
        with self.assertRaises(ValidationError):
            self.bom_int_prod_y.get_factor_to_product(self.end_prod_b_red)

    def test_get_factor_to_product_multiple_lines(self):
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.int_prod_x_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.bulk_material.id,
                            "product_qty": 3.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.bulk_material.id,
                            "product_qty": 3.0,
                        },
                    ),
                ],
            }
        )

        with self.assertRaises(ValidationError):
            bom.get_factor_to_product(self.bulk_material)

    def test_get_factor_to_product_bom_multiple_1(self):
        FACTOR = 3.0 / 1.0  # 1 unit requires 3 units
        self.assertEqual(
            self.bom_int_prod_y.get_factor_to_product(self.bulk_material), FACTOR
        )

    def test_get_factor_to_product_bom_multiple_not_1(self):
        FACTOR = 6.0 / 2.0  # 2 units requires 6 units -> 1 unit requires 3 units

        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.int_prod_x_tmpl.id,
                "product_qty": 2.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.bulk_material.id,
                            "product_qty": 6.0,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(bom.get_factor_to_product(self.bulk_material), FACTOR)
