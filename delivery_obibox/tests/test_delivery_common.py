from datetime import datetime

from odoo.tests import common

from ..models.obibox_request import ObiboxProvider


class TestDeliveryCommon(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.sr = ObiboxProvider(
            None, self.env, prod_environment=False, username="test", token="test"
        )

        location_id = self.ref("stock.stock_location_stock")
        self.location = self.env["stock.location"].browse(location_id)
        self.partner_location = self.env["stock.location"].browse(
            self.ref("stock.stock_location_customers")
        )
        delivery_product = self.env["product.product"].create(
            {
                "name": "Delivery Product",
                "type": "service",
            }
        )

        self.obibox_method = self.env["delivery.carrier"].create(
            {
                "name": "Obibox",
                "delivery_type": "obibox",
                "integration_level": "rate_and_ship",
                "product_id": delivery_product.id,
                "obibox_api_key": "test_api_key",
                "obibox_username": "test_username",
                "obibox_label_format": "zpl",
                "obibox_delivery_day": "wed",
            }
        )

        self.package_type = self.env["stock.package.type"].create(
            {
                "name": "Test Package Type",
                "base_weight": 0.1,
                "height": 254,
                "packaging_length": 254,
                "width": 254,
            }
        )

        self.productA = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "weight": 0.1,
            }
        )
        self.productB = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "weight": 0.1,
            }
        )
        self.out = self.env["stock.picking.type"].browse(
            self.ref("stock.picking_type_out")
        )

        uom = self.env["uom.uom"]
        self.in_uom = uom.browse(self.ref("uom.product_uom_inch"))
        self.ft_uom = uom.browse(self.ref("uom.product_uom_foot"))
        self.lb_uom = uom.browse(self.ref("uom.product_uom_lb"))
        self.package_w_uom = uom.search(
            [("name", "=", self.package_type.weight_uom_name)]
        )[0]

        self.package_l_uom = uom.search(
            [("name", "=", self.package_type.length_uom_name)]
        )[0]

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Client",
                "street": "1010 avenue test",
                "street2": "App 1010",
                "city": "TestVille",
                "state_id": self.env["res.country.state"]
                .search([("code", "=", "QC")])[0]
                .id,
                "zip": "H0H0H0",
                "phone": "4181234567",
                "email": "test@test.com",
            }
        )

        # Ensure company has required fields
        self.env.company.write(
            {
                "phone": "5141234567",
                "email": "company@test.com",
                "state_id": self.partner.state_id.id,
                "country_id": self.env["res.country"]
                .search([("code", "=", "CA")], limit=1)
                .id,
                "zip": "H1H1H1",
                "city": "Montreal",
                "street": "123 Main St",
            }
        )

    def get_package_values(self, package):
        package_l = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.in_uom
        )
        package_h = self.package_l_uom._compute_quantity(
            self.package_type.height, self.in_uom
        )
        package_w = self.package_l_uom._compute_quantity(
            self.package_type.width, self.in_uom
        )

        package_l_ft = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.ft_uom
        )
        package_h_ft = self.package_l_uom._compute_quantity(
            self.package_type.height, self.ft_uom
        )
        package_w_ft = self.package_l_uom._compute_quantity(
            self.package_type.width, self.ft_uom
        )

        volume = package_l_ft * package_h_ft * package_w_ft
        long_side = max(package_l, package_h, package_w)
        weight = self.package_w_uom._compute_quantity(
            package.shipping_weight, self.lb_uom
        )
        return volume, long_side, weight

    def make_picking(self, n_packages=1, contact=None):
        if not contact:
            contact = self.partner

        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.partner_location.id,
                "picking_type_id": self.out.id,
                "partner_id": contact.id,
                "carrier_id": self.obibox_method.id,
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 10,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
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
                "product_id": self.productA.id,
                "product_uom": self.productA.uom_id.id,
                "product_uom_qty": 10,
                "picking_id": picking.id,
            }
        )
        if n_packages > 1:
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
        self.assertEqual(len(picking.move_ids), n_packages)

        smlA = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.productA)
        smlA.write({"quantity": 10.0, "picked": True})
        quantA = smlA.quant_id

        pack1 = self.env["stock.package"].create(
            {"package_type_id": self.package_type.id, "quant_ids": [quantA.id]}
        )
        smlA.result_package_id = pack1.id

        if n_packages > 1:
            smlB = picking.move_line_ids.filtered(
                lambda ml: ml.product_id == self.productB
            )
            smlB.quantity = 10
            smlB.picked = True
            quantB = smlB.quant_id
            pack2 = self.env["stock.package"].create(
                {"package_type_id": self.package_type.id, "quant_ids": [quantB.id]}
            )
            smlB.result_package_id = pack2.id
        return picking
