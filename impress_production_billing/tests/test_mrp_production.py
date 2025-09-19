from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestMrpProduction(TransactionCase):
    def setUp(self):
        super().setUp()

        self.product_model = self.env["product.product"]
        self.mo_model = self.env["mrp.production"]
        self.so_model = self.env["sale.order"]
        self.so_line_model = self.env["sale.order.line"]
        self.bom_model = self.env["mrp.bom"]

        self.partner = self.env["res.partner"].create({"name": "test partner"})

        self.billing_product = self.product_model.create(
            {"name": "Billing Product", "type": "service"}
        )

        self.product = self.product_model.create(
            {
                "name": "Test Product",
                "type": "consu",
            }
        )

        self.bom = self.bom_model.create(
            {
                "product_id": self.product.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "billing_product_id": self.billing_product.id,
            }
        )

    def test_link_mo_to_so_all_correct(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        so_line = self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        self.assertEqual(mo.billing_sale_order_id, so)
        self.assertEqual(mo.billing_sale_order_line_id, so_line)

    def test_link_mo_to_so_wrong_product(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
            }
        )

        self.assertRaises(
            ValidationError,
            self.mo_model.create,
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            },
        )

    def test_link_mo_to_so_no_line(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )

        self.assertRaises(
            ValidationError,
            self.mo_model.create,
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            },
        )

    def test_link_mo_to_so_wrong_reference(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )

        self.assertRaises(
            ValidationError,
            self.mo_model.create,
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": "WRONG_REF",
            },
        )

    def test_mo_produce_delivered_qty(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        so_line = self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        mo.button_mark_done()

        self.assertEqual(so_line.qty_delivered, 1)

    def test_mo_produce_delivered_qty_multiple(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        so_line = self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo_1 = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )
        mo_2 = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        mo_1.button_mark_done()
        self.assertEqual(so_line.qty_delivered, 1)
        mo_2.button_mark_done()
        self.assertEqual(so_line.qty_delivered, 2)

    def test_mo_produce_delivered_qty_unbuild(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        so_line = self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        mo.button_mark_done()

        self.assertEqual(so_line.qty_delivered, 1)

        unbuild = self.env["mrp.unbuild"].create(
            {"product_id": self.product.id, "product_qty": 1, "mo_id": mo.id}
        )
        unbuild.action_unbuild()
        self.assertEqual(so_line.qty_delivered, 0)

    def test_mo_produced_delivered_qty_unbuild_multiple(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        so_line = self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo_1 = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )
        mo_2 = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        mo_1.button_mark_done()
        mo_2.button_mark_done()
        self.assertEqual(so_line.qty_delivered, 2)

        unbuild_1 = self.env["mrp.unbuild"].create(
            {"product_id": self.product.id, "product_qty": 1, "mo_id": mo_1.id}
        )
        unbuild_1.action_unbuild()
        self.assertEqual(so_line.qty_delivered, 1)

        unbuild_2 = self.env["mrp.unbuild"].create(
            {"product_id": self.product.id, "product_qty": 1, "mo_id": mo_2.id}
        )
        unbuild_2.action_unbuild()
        self.assertEqual(so_line.qty_delivered, 0)

    def test_mo_cancel(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )

        self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        mo._action_cancel()

        self.assertEqual(
            mo.billing_sale_order_id, self.so_model
        )  # Checks if billing_sale_order_id is an empty recordset
        self.assertEqual(mo.billing_sale_order_line_id, self.so_line_model)
        self.assertEqual(mo.billing_sale_order_ref, False)
