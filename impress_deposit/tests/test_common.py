from odoo.tests import TransactionCase


class TestCommon(TransactionCase):
    def setUp(self):
        super().setUp()

        self.so_model = self.env["sale.order"]
        self.sol_model = self.env["sale.order.line"]
        self.product_model = self.env["product.product"]
        self.partner_model = self.env["res.partner"]

        self.deposit_product = self.product_model.create(
            {"name": "Deposit Product", "type": "service", "invoice_policy": "delivery"}
        )

        self.config = self.env["res.config.settings"].create(
            {"deposit_product": self.deposit_product.id}
        )

        self.product_w_deposit = self.product_model.create(
            {
                "name": "Product with Deposit",
                "type": "product",
                "requires_deposit": True,
                "qty_multiple": 1,
            }
        )
        self.product_wo_deposit = self.product_model.create(
            {
                "name": "Product without Deposit",
                "type": "product",
                "requires_deposit": False,
                "qty_multiple": 1,
            }
        )

        self.partner_w_deposit = self.partner_model.create(
            {"name": "Partner with Deposit", "requires_deposit": True}
        )
        self.partner_wo_deposit = self.partner_model.create(
            {"name": "Partner without Deposit", "requires_deposit": False}
        )

        self.wh = self.env.ref("stock.warehouse0")

        self.env["stock.quant"].create(
            {
                "product_id": self.product_w_deposit.id,
                "location_id": self.wh.lot_stock_id.id,
                "quantity": 100,
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.product_wo_deposit.id,
                "location_id": self.wh.lot_stock_id.id,
                "quantity": 100,
            }
        )
