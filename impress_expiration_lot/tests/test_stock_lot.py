from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestStockLot(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "detailed_type": "product",
                "tracking": "lot",
                "use_expiration_date": True,
                "expiration_time": 20,
                "use_time": 10,
                "removal_time": 2,
                "alert_time": 5,
                "default_code": "EXXXXX",
            }
        )

    def test_create_lot(self):
        date = datetime.strptime("2025-01-01", "%Y-%m-%d")
        lot = self.env["stock.lot"].create(
            {"name": "25001", "product_id": self.product.id}
        )

        exp_date = date + timedelta(days=self.product.expiration_time + 1)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time + 1)
        alert_date = exp_date - timedelta(days=self.product.alert_time + 1)

        lot._calculate_expiration_date()

        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())
