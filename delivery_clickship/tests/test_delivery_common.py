from datetime import datetime

from odoo.tests import common

from ..models.clickship_request import ClickshipProvider


class TestDeliveryCommon(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.sr = ClickshipProvider(
            debug_logger=lambda msg, name: None,
            prod_environment=False,
            token="test_token",
        )

        location_id = self.ref("stock.stock_location_stock")
        self.location = self.env["stock.location"].browse(location_id)
        self.partner_location = self.env["stock.location"].browse(
            self.ref("stock.stock_location_customers")
        )

        # Create delivery product
        delivery_product = self.env["product.product"].create(
            {
                "name": "Delivery Product",
                "type": "service",
            }
        )

        # Create HR Employee for contact
        self.contact = self.env["hr.employee"].create(
            {
                "name": "Test Contact",
                "work_phone": "+1-514-555-0123",
            }
        )

        # Create payment method
        self.payment_method = self.env["clickship.payment_method"].create(
            {
                "name": "Test Payment Method",
                "code": "test_payment_method",
            }
        )

        # Create clickship delivery carrier
        self.clickship_method = self.env["delivery.carrier"].create(
            {
                "name": "ClickShip",
                "delivery_type": "clickship",
                "integration_level": "rate_and_ship",
                "product_id": delivery_product.id,
                "clickship_api_key": "test_api_key",
                "clickship_contact": self.contact.id,
                "clickship_payment_method": self.payment_method.id,
            }
        )

        # Link payment method to carrier
        self.payment_method.delivery_carrier_id = self.clickship_method.id

        # Create package type
        self.package_type = self.env["stock.package.type"].create(
            {
                "name": "Test Package Type",
                "base_weight": 0.1,
                "height": 254,
                "packaging_length": 254,
                "width": 254,
            }
        )

        # Create test products
        self.productA = self.env["product.product"].create(
            {
                "name": "Test Product A",
                "type": "product",
                "weight": 0.1,
            }
        )
        self.productB = self.env["product.product"].create(
            {
                "name": "Test Product B",
                "type": "product",
                "weight": 0.2,
            }
        )

        # Get picking types and UOMs
        self.out = self.env["stock.picking.type"].browse(
            self.ref("stock.picking_type_out")
        )

        uom = self.env["uom.uom"]
        self.in_uom = uom.browse(self.ref("uom.product_uom_inch"))
        self.ft_uom = uom.browse(self.ref("uom.product_uom_foot"))
        self.lb_uom = uom.browse(self.ref("uom.product_uom_lb"))
        self.kg_uom = uom.browse(self.ref("uom.product_uom_kgm"))
        self.mm_uom = uom.search([("name", "=", "mm")], limit=1)
        if not self.mm_uom:
            self.mm_uom = uom.create(
                {"name": "mm", "category_id": self.ref("uom.uom_categ_length")}
            )

        self.package_w_uom = uom.search(
            [("name", "=", self.package_type.weight_uom_name)]
        )
        if not self.package_w_uom:
            self.package_w_uom = self.kg_uom

        self.package_l_uom = uom.search(
            [("name", "=", self.package_type.length_uom_name)]
        )
        if not self.package_l_uom:
            self.package_l_uom = self.mm_uom

        # Create test partner
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Client",
                "street": "1010 avenue test",
                "street2": "App 1010",
                "city": "TestVille",
                "state_id": self.env["res.country.state"]
                .search([("code", "=", "QC")], limit=1)
                .id,
                "country_id": self.env["res.country"].search([("code", "=", "CA")]).id,
                "zip": "H0H0H0",
                "phone": "4181234567",
                "email": "test@test.com",
            }
        )

    def make_picking(self, n_packages=1, contact=None):
        """Create a test picking with packages"""
        if not contact:
            contact = self.partner
        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.partner_location.id,
                "picking_type_id": self.out.id,
                "partner_id": contact.id,
                "carrier_id": self.clickship_method.id,
            }
        )

        # Create stock quants
        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 10,
                "location_id": self.location.id,
                "in_date": datetime.now(),
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

        # Create stock moves
        self.env["stock.move"].create(
            {
                "location_dest_id": self.partner_location.id,
                "location_id": self.location.id,
                "name": "Test Move A",
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
                    "name": "Test Move B",
                    "product_id": self.productB.id,
                    "product_uom": self.productB.uom_id.id,
                    "product_uom_qty": 10,
                    "picking_id": picking.id,
                }
            )

        # Confirm and assign picking
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(len(picking.move_ids_without_package), n_packages)

        # Create packages
        smlA = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.productA)
        smlA.write({"quantity": 10.0, "picked": True})
        quantA = smlA.quant_id

        pack1 = self.env["stock.quant.package"].create(
            {"package_type_id": self.package_type.id, "quant_ids": [quantA.id]}
        )
        smlA.result_package_id = pack1.id

        self.assertEqual(len(picking.package_ids), 1)

        if n_packages > 1:
            smlB = picking.move_line_ids.filtered(
                lambda ml: ml.product_id == self.productB
            )
            smlB.quantity = 10
            smlB.picked = True
            quantB = smlB.quant_id
            pack2 = self.env["stock.quant.package"].create(
                {"package_type_id": self.package_type.id, "quant_ids": [quantB.id]}
            )
            smlB.result_package_id = pack2.id
            self.assertEqual(len(picking.package_ids), 2)

        return picking

    def make_sale_order(self):
        """Create a test sale order"""
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "carrier_id": self.clickship_method.id,
            }
        )
