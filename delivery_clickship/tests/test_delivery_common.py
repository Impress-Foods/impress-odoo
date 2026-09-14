from datetime import datetime

from odoo.tests import TransactionCase

from ..models.clickship_request import ClickshipProvider


class TestDeliveryCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        debug_logger = cls.browse_ref(
            cls, "delivery_clickship.delivery_carrier_clickship"
        )

        cls.sr = ClickshipProvider(
            debug_logger=debug_logger.log_xml,
            env=cls.env,
            prod_environment=False,
            token="test_token",
        )

        cls.location = cls.browse_ref(cls, "stock.stock_location_stock")
        cls.partner_location = cls.browse_ref(cls, "stock.stock_location_customers")

        # Create delivery product
        delivery_product = cls.env["product.product"].create(
            {
                "name": "Delivery Product",
                "type": "service",
            }
        )

        # Create HR Employee for contact
        cls.contact = cls.env["hr.employee"].create(
            {
                "name": "Test Contact",
                "work_phone": "+1-514-555-0123",
                "email": "test@test.com",
            }
        )

        # Create payment method
        cls.payment_method = cls.env["clickship.payment_method"].create(
            {
                "name": "Test Payment Method",
                "code": "test_payment_method",
            }
        )

        # Create clickship delivery carrier
        cls.clickship_method = cls.env["delivery.carrier"].create(
            {
                "name": "ClickShip",
                "delivery_type": "clickship",
                "integration_level": "rate_and_ship",
                "product_id": delivery_product.id,
                "clickship_api_key": "test_api_key",
                "clickship_contact": cls.contact.id,
                "clickship_payment_method": cls.payment_method.id,
            }
        )

        # Link payment method to carrier
        cls.payment_method.delivery_carrier_id = cls.clickship_method.id

        # Create package type
        cls.package_type = cls.env["stock.package.type"].create(
            {
                "name": "Test Package Type",
                "base_weight": 0.1,
                "height": 254,
                "packaging_length": 254,
                "width": 254,
            }
        )

        # Create test products
        cls.productA = cls.env["product.product"].create(
            {
                "name": "Test Product A",
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

        # Get picking types and UOMs
        cls.out = cls.browse_ref(cls, "stock.picking_type_out")

        cls.in_uom = cls.browse_ref(cls, "uom.product_uom_inch")
        cls.ft_uom = cls.browse_ref(cls, "uom.product_uom_foot")
        cls.lb_uom = cls.browse_ref(cls, "uom.product_uom_lb")
        cls.kg_uom = cls.browse_ref(cls, "uom.product_uom_kgm")
        cls.mm_uom = cls.browse_ref(cls, "uom.product_uom_millimeter")
        cls.package_w_uom = cls.kg_uom
        cls.package_l_uom = cls.mm_uom

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Client",
                "street": "1010 avenue test",
                "street2": "App 1010",
                "city": "TestVille",
                "state_id": cls.env["res.country.state"]
                .search([("code", "=", "QC")], limit=1)
                .id,
                "country_id": cls.env["res.country"].search([("code", "=", "CA")]).id,
                "zip": "H0H0H0",
                "phone": "4181234567",
                "email": "test@test.com",
            }
        )
        cls.browse_ref(cls, "base.CAD").active = True
        company = cls.browse_ref(cls, "base.main_company")
        company.phone = "4181234567"
        company.email = "test@test.com"
        company.state_id = cls.browse_ref(cls, "base.state_ca_qc")
        company.country_id = cls.browse_ref(cls, "base.ca")

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

        # Confirm and assign picking
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(len(picking.move_ids), n_packages)

        # Create packages
        smlA = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.productA)
        smlA.write({"quantity": 10.0, "picked": True})
        quantA = smlA.quant_id

        pack1 = self.env["stock.package"].create(
            {"package_type_id": self.package_type.id, "quant_ids": [quantA.id]}
        )
        smlA.result_package_id = pack1.id

        self.assertEqual(len(picking._get_packages()), 1)

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
            self.assertEqual(len(picking._get_packages()), 2)

        return picking

    def make_sale_order(self):
        """Create a test sale order"""
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "carrier_id": self.clickship_method.id,
            }
        )
