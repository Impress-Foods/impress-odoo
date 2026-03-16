from .test_common import TestCommon


class TestSaleOrder(TestCommon):
    def test_is_deposit_line_true(self) -> None:
        so = self.so_model.create({"partner_id": self.partner_w_deposit.id})
        line = self.sol_model.create(
            {
                "product_id": self.deposit_product.id,
                "order_id": so.id,
                "product_uom_id": 1.0,
            }
        )
        self.assertTrue(line.is_deposit_line)

    def test_is_deposit_line_false(self) -> None:
        so = self.so_model.create({"partner_id": self.partner_w_deposit.id})
        line = self.sol_model.create(
            {
                "product_id": self.product_w_deposit.id,
                "order_id": so.id,
                "product_uom_id": 1.0,
            }
        )
        self.assertFalse(line.is_deposit_line)
