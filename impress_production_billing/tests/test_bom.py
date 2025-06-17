from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestProductProduct(TransactionCase):
    def setUp(self):
        super().setUp()

        self.product_model = self.env["product.product"]
        self.bom_model = self.env["mrp.bom"]

        self.billing_product = self.product_model.create(
            {"name": "Billing Product", "type": "service", "default_code": "SPP1"}
        )

        self.product = self.product_model.create(
            {
                "name": "Billing Product",
                "type": "consu",
                "default_code": "EPP1",
            }
        )

        self.bom_with_billing_product = self.bom_model.create(
            {
                "product_id": self.product.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "billing_product_id": self.billing_product.id,
            }
        )

        self.bom_without_billing_product = self.bom_model.create(
            {
                "product_id": self.product.id,
                "product_tmpl_id": self.product.product_tmpl_id.id,
            }
        )

    def test_get_billing_product_billing_product_id_field(self):
        self.assertEqual(
            self.bom_with_billing_product.get_production_billing_product(),
            self.billing_product,
        )

    def test_get_billing_product_reference_matching(self):
        self.assertEqual(
            self.bom_without_billing_product.get_production_billing_product(),
            self.billing_product,
        )
