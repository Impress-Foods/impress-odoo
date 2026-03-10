from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestProductProduct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_model = cls.env["product.product"]
        cls.bom_model = cls.env["mrp.bom"]

        cls.billing_product = cls.product_model.create(
            {"name": "Billing Product", "type": "service", "default_code": "SPP1"}
        )

        cls.product = cls.product_model.create(
            {
                "name": "Billing Product",
                "type": "product",
                "default_code": "EPP1",
            }
        )

        cls.bom_with_billing_product = cls.bom_model.create(
            {
                "product_id": cls.product.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "billing_product_id": cls.billing_product.id,
            }
        )

        cls.bom_without_billing_product = cls.bom_model.create(
            {
                "product_id": cls.product.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
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
