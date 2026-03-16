from odoo.tests import TransactionCase


class TestCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.so_model = cls.env["sale.order"]
        cls.sol_model = cls.env["sale.order.line"]
        cls.product_model = cls.env["product.product"]
        cls.partner_model = cls.env["res.partner"]

        unit_uom = cls.env["uom.uom"].search([("name", "=", "Units")])

        cls.deposit_product = cls.product_model.create(
            {
                "name": "Deposit Product",
                "type": "service",
                "invoice_policy": "delivery",
                "uom_id": unit_uom.id,
            }
        )

        cls.config = (
            cls.env["res.config.settings"]
            .create({"deposit_product": cls.deposit_product.id})
            .execute()
        )

        cls.product_w_deposit = cls.product_model.create(
            {
                "name": "Product with Deposit",
                "type": "consu",
                "is_storable": True,
                "requires_deposit": True,
                "qty_multiple": 1,
            }
        )
        cls.product_wo_deposit = cls.product_model.create(
            {
                "name": "Product without Deposit",
                "type": "consu",
                "is_storable": True,
                "requires_deposit": False,
                "qty_multiple": 1,
            }
        )

        cls.partner_w_deposit = cls.partner_model.create(
            {"name": "Partner with Deposit", "requires_deposit": True}
        )
        cls.partner_wo_deposit = cls.partner_model.create(
            {"name": "Partner without Deposit", "requires_deposit": False}
        )

        cls.wh = cls.env.ref("stock.warehouse0")
        cls.delivery_type = cls.env.ref("stock.picking_type_out")

        cls.env["stock.quant"].create(
            {
                "product_id": cls.product_w_deposit.id,
                "location_id": cls.wh.lot_stock_id.id,
                "quantity": 100,
            }
        )
        cls.env["stock.quant"].create(
            {
                "product_id": cls.product_wo_deposit.id,
                "location_id": cls.wh.lot_stock_id.id,
                "quantity": 100,
            }
        )
