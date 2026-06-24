from unittest.mock import patch

from odoo.tests import common

from odoo.addons.base.models.res_partner import ResPartner
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale.models.sale_order_line import SaleOrderLine


class TestSaleOrder(common.TransactionCase):
    def setUp(self) -> None:
        super().setUp()

        self.env["ir.config_parameter"].sudo().set_param(
            "delivery_auto_select_carrier.domain", [("origin", "=", "test")]
        )
        self.carrier_model = self.env["delivery.carrier"]
        self.so_model: SaleOrder = self.env["sale.order"]
        self.product_model = self.env["product.product"]
        self.partner_model: ResPartner = self.env["res.partner"]
        self.sol_model: SaleOrderLine = self.env["sale.order.line"]
        self.delivery_product = self.product_model.create(
            {
                "name": "Delivery Product",
                "type": "service",
            }
        )

        self.sale_product = self.product_model.create(
            {"name": "Sale Product", "type": "consu", "is_storable": True}
        )

        zip_prefix_1 = self.env["delivery.zip.prefix"].create(
            {
                "name": "G2",
            }
        )

        zip_prefix_2 = self.env["delivery.zip.prefix"].create(
            {
                "name": "H",
            }
        )
        self.carrier_G2 = self.carrier_model.create(
            {
                "name": "Carrier G2",
                "delivery_type": "fixed",
                "product_id": self.delivery_product.id,
                "can_be_auto_selected": True,
                "country_ids": [self.env.ref("base.ca").id],
                "zip_prefix_ids": [zip_prefix_1.id],
                "priority": 99,
            }
        )
        self.carrier_H = self.carrier_model.create(
            {
                "name": "Carrier H",
                "delivery_type": "fixed",
                "product_id": self.delivery_product.id,
                "can_be_auto_selected": True,
                "country_ids": [self.env.ref("base.ca").id],
                "zip_prefix_ids": [zip_prefix_2.id],
                "priority": 95,
            }
        )
        self.carrier_no_prefix = self.carrier_model.create(
            {
                "name": "Carrier No Prefix",
                "delivery_type": "fixed",
                "product_id": self.delivery_product.id,
                "can_be_auto_selected": True,
                "priority": 90,
            }
        )
        self.carrier_model.create(
            {
                "name": "Carrier Not Auto Select",
                "delivery_type": "fixed",
                "product_id": self.delivery_product.id,
                "can_be_auto_selected": False,
                "priority": 100,
            }
        )
        self.partner_G2 = self.partner_model.create(
            {
                "name": "G2",
                "street": "42 rue Test",
                "city": "Québec",
                "state_id": self.env.ref("base.state_ca_qc").id,
                "country_id": self.env.ref("base.ca").id,
                "zip": "G2G2G2",
                "phone": "5555555555",
            }
        )
        self.partner_H = self.partner_model.create(
            {
                "name": "H",
                "street": "42 rue Test",
                "city": "Québec",
                "state_id": self.env.ref("base.state_ca_qc").id,
                "country_id": self.env.ref("base.ca").id,
                "zip": "H2H2H2",
                "phone": "5555555555",
            }
        )
        self.partner_J = self.partner_model.create(
            {
                "name": "J",
                "street": "42 rue Test",
                "city": "Québec",
                "state_id": self.env.ref("base.state_ca_qc").id,
                "country_id": self.env.ref("base.ca").id,
                "zip": "J2J2J2",
                "phone": "5555555555",
            }
        )

    def setup_sale_order(self, partner: ResPartner) -> SaleOrder:
        sale_order = self.so_model.create(
            {
                "partner_id": partner.id,
                "partner_shipping_id": partner.id,
                "partner_invoice_id": partner.id,
                "origin": "test",
            }
        )
        self.sol_model.create(
            {
                "order_id": sale_order.id,
                "product_id": self.sale_product.id,
                "product_uom_qty": 1,
                "product_uom_id": self.sale_product.uom_id.id,
                "name": "test",
            }
        )
        return sale_order

    def test_auto_select_carrier_outside_domain(self) -> None:
        sale_order = self.setup_sale_order(self.partner_G2)
        sale_order.origin = "something else"
        sale_order._compute_auto_selected_carrier_id()
        sale_order.action_confirm()
        self.assertEqual(sale_order.auto_selected_carrier_id, self.carrier_model)

    def test_auto_select_carrier_top_priority(self) -> None:
        sale_order = self.setup_sale_order(self.partner_G2)
        sale_order.action_confirm()
        self.assertEqual(sale_order.auto_selected_carrier_id, self.carrier_G2)

    def test_auto_select_carrier_manual(self) -> None:
        sale_order = self.setup_sale_order(self.partner_G2)
        sale_order.action_confirm()
        sale_order.auto_selected_carrier_id = False
        sale_order.action_auto_select_carrier()
        self.assertEqual(sale_order.auto_selected_carrier_id, self.carrier_G2)

    def test_auto_select_carrier_lower_priority(self) -> None:
        sale_order = self.setup_sale_order(self.partner_H)
        sale_order.action_confirm()
        self.assertEqual(sale_order.auto_selected_carrier_id, self.carrier_H)

    def test_auto_select_carrier_no_prefix(self) -> None:
        sale_order = self.setup_sale_order(self.partner_J)
        sale_order.action_confirm()
        self.assertEqual(sale_order.auto_selected_carrier_id, self.carrier_no_prefix)

    def test_carrier_propagation_to_picking(self) -> None:
        sale_order = self.setup_sale_order(self.partner_G2)
        sale_order.action_confirm()
        picking = sale_order.picking_ids
        self.assertEqual(picking.carrier_id, self.carrier_G2)

        sale_order = self.setup_sale_order(self.partner_J)
        sale_order.origin = "something_else"
        sale_order.action_confirm()
        picking = sale_order.picking_ids
        self.assertEqual(picking.carrier_id, self.carrier_model)

    @patch(
        "odoo.addons.delivery.models.delivery_carrier.DeliveryCarrier.available_carriers"
    )
    def test_no_auto_select_carriers(self, mock_available_carriers):
        mock_available_carriers.return_value = self.carrier_model

        sale_order = self.setup_sale_order(self.partner_J)
        sale_order.action_confirm()
        picking = sale_order.picking_ids
        self.assertEqual(picking.carrier_id, self.carrier_model)
