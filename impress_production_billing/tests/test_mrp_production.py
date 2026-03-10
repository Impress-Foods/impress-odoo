from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestMrpProduction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_model = cls.env["product.product"]
        cls.mo_model = cls.env["mrp.production"]
        cls.so_model = cls.env["sale.order"]
        cls.so_line_model = cls.env["sale.order.line"]
        cls.bom_model = cls.env["mrp.bom"]

        cls.partner = cls.env["res.partner"].create({"name": "test partner"})

        cls.billing_product = cls.product_model.create(
            {"name": "Billing Product", "type": "service"}
        )

        cls.product = cls.product_model.create(
            {
                "name": "Test Product",
                "type": "product",
            }
        )

        cls.bom = cls.bom_model.create(
            {
                "product_id": cls.product.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "billing_product_id": cls.billing_product.id,
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

        with self.assertRaises(ValidationError):
            self.mo_model.create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "billing_sale_order_ref": reference,
                }
            )

    def test_link_mo_to_so_no_line(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )

        with self.assertRaises(ValidationError):
            self.mo_model.create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "billing_sale_order_ref": reference,
                }
            )

    def test_link_mo_to_so_wrong_reference(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )

        with self.assertRaises(ValidationError):
            self.mo_model.create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "billing_sale_order_ref": "WRONG_REF",
                }
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
        unbuild.action_validate()
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
        unbuild_1.action_validate()
        self.assertEqual(so_line.qty_delivered, 1)

        unbuild_2 = self.env["mrp.unbuild"].create(
            {"product_id": self.product.id, "product_qty": 1, "mo_id": mo_2.id}
        )
        unbuild_2.action_validate()
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

        self.assertEqual(mo.billing_sale_order_id, self.so_model)
        self.assertEqual(mo.billing_sale_order_line_id, self.so_line_model)
        self.assertEqual(mo.billing_sale_order_ref, False)

    def test_change_mo_product_after_so_reference_set(self):
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

        product_b = self.product_model.create(
            {"name": "Product B", "type": "product", "default_code": "PB01"}
        )
        billing_product_b = self.product_model.create(
            {"name": "Billing Product B", "type": "service", "default_code": "SB01"}
        )
        self.bom_model.create(
            {
                "product_id": product_b.id,
                "product_tmpl_id": product_b.product_tmpl_id.id,
                "billing_product_id": billing_product_b.id,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference,
            }
        )

        self.assertEqual(mo.billing_sale_order_line_id, so_line)

        mo.product_id = product_b.id

        self.assertFalse(
            mo.billing_sale_order_line_id,
            "MO should be unlinked from SO line when product changes "
            "and no matching line exists",
        )

    def test_change_so_line_product(self):
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

        self.assertEqual(mo.billing_sale_order_line_id, so_line)

        other_product = self.product_model.create(
            {"name": "Other Product", "type": "service"}
        )
        so_line.product_id = other_product.id

        self.assertFalse(
            mo.billing_sale_order_line_id,
            "MO should be unlinked from SO line when line product changes",
        )

    def test_multiple_so_lines_same_billing_product(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        so = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
                "name": "First line",
            }
        )
        self.so_line_model.create(
            {
                "order_id": so.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 2,
                "name": "Second line",
            }
        )

        with self.assertRaises(ValidationError) as ctx:
            self.mo_model.create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "billing_sale_order_ref": reference,
                }
            )

        self.assertIn(
            "Multiple",
            str(ctx.exception.args[0]),
            "Should raise error about multiple matching lines",
        )

    def test_change_so_reference_to_different_so(self):
        reference_1 = hash(datetime.now().strftime("%Y%m%d%H%M%S"))
        reference_2 = hash(datetime.now().strftime("%Y%m%d%H%M%S")) + 1

        so_1 = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference_1}
        )
        so_line_1 = self.so_line_model.create(
            {
                "order_id": so_1.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        so_2 = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference_2}
        )
        so_line_2 = self.so_line_model.create(
            {
                "order_id": so_2.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        mo = self.mo_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "billing_sale_order_ref": reference_1,
            }
        )

        self.assertEqual(mo.billing_sale_order_id, so_1)
        self.assertEqual(mo.billing_sale_order_line_id, so_line_1)

        mo.billing_sale_order_ref = str(reference_2)

        self.assertEqual(mo.billing_sale_order_id, so_2)
        self.assertEqual(mo.billing_sale_order_line_id, so_line_2)

    def test_duplicate_so_with_same_client_order_ref(self):
        reference = hash(datetime.now().strftime("%Y%m%d%H%M%S"))

        so_1 = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        self.so_line_model.create(
            {
                "order_id": so_1.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 1,
            }
        )

        so_2 = self.so_model.create(
            {"partner_id": self.partner.id, "client_order_ref": reference}
        )
        self.so_line_model.create(
            {
                "order_id": so_2.id,
                "product_id": self.billing_product.id,
                "product_uom_qty": 5,
            }
        )

        with self.assertRaises(ValidationError):
            self.mo_model.create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                    "billing_sale_order_ref": str(reference),
                }
            )

    def test_so_line_unlink_cascades_to_mo(self):
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

        self.assertEqual(mo.billing_sale_order_line_id, so_line)

        so_line.unlink()

        self.assertFalse(
            mo.billing_sale_order_line_id,
            "MO should be unlinked when SO line is deleted",
        )
