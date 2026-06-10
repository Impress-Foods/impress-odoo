from datetime import datetime

from odoo.tests import common


class TestDeliveryCommon(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.location = cls.env.ref("stock.stock_location_stock")

        cls.partner_location = cls.env.ref("stock.stock_location_customers")

        cls.out = cls.env.ref("stock.picking_type_out")

        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "weight": 0.1,
            }
        )
        cls.productB = cls.env["product.product"].create(
            {
                "name": "Test Product B",
                "type": "consu",
                "is_storable": True,
                "weight": 0.2,
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Client",
                "street": "1010 avenue test",
                "city": "TestVille",
                "zip": "H0H0H0",
                "phone": "4181234567",
                "email": "test@test.com",
            }
        )

        cls.package_type = cls.env["stock.package.type"].create(
            {
                "name": "Test Package Type",
                "base_weight": 0.1,
                "height": 254,
                "packaging_length": 254,
                "width": 254,
            }
        )

    def make_picking(self, n_packages=1):
        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.partner_location.id,
                "picking_type_id": self.out.id,
                "partner_id": self.partner.id,
            }
        )

        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )

        self.env["stock.move"].create(
            {
                "location_dest_id": self.partner_location.id,
                "location_id": self.location.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 10,
                "picking_id": picking.id,
            }
        )

        if n_packages > 1:
            self.env["stock.quant"].create(
                {
                    "product_id": self.productB.id,
                    "quantity": 10,
                    "location_id": self.location.id,
                    "in_date": datetime.now(),
                }
            )
            self.env["stock.move"].create(
                {
                    "location_dest_id": self.partner_location.id,
                    "location_id": self.location.id,
                    "product_id": self.productB.id,
                    "product_uom": self.productB.uom_id.id,
                    "product_uom_qty": 10,
                    "picking_id": picking.id,
                }
            )

        picking.action_confirm()
        picking.action_assign()

        smlA = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.product)
        smlA.write({"quantity": 10.0, "picked": True})
        pack1 = self.env["stock.package"].create(
            {"package_type_id": self.package_type.id, "quant_ids": [smlA.quant_id.id]}
        )
        smlA.result_package_id = pack1.id

        if n_packages > 1:
            smlB = picking.move_line_ids.filtered(
                lambda ml: ml.product_id == self.productB
            )
            smlB.write({"quantity": 10.0, "picked": True})
            pack2 = self.env["stock.package"].create(
                {
                    "package_type_id": self.package_type.id,
                    "quant_ids": [smlB.quant_id.id],
                }
            )
            smlB.result_package_id = pack2.id

        return picking
