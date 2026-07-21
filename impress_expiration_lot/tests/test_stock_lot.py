from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestStockLot(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
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
        """Checks if dates are calculated on lot creation"""
        date = datetime.strptime("2025-01-01", "%Y-%m-%d")
        lot = self.env["stock.lot"].create(
            {"name": "25001", "product_id": self.product.id}
        )

        exp_date = date + timedelta(days=self.product.expiration_time)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time)
        alert_date = exp_date - timedelta(days=self.product.alert_time)

        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())

    def test_write_lot(self):
        """Checks if dates are recalculated on name change"""
        date = datetime.strptime("2025-02-01", "%Y-%m-%d")
        lot = self.env["stock.lot"].create(
            {"name": "25001", "product_id": self.product.id}
        )
        lot.write({"name": "25032"})

        exp_date = date + timedelta(days=self.product.expiration_time)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time)
        alert_date = exp_date - timedelta(days=self.product.alert_time)

        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())

    @freeze_time("2025-01-01")
    def test_invalid_lot_number(self):
        """Checks if invalid lot number uses default behavior"""
        date = datetime.today()
        lot = self.env["stock.lot"].create(
            {"name": "A15477", "product_id": self.product.id}
        )
        exp_date = date + timedelta(days=self.product.expiration_time)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time)
        alert_date = exp_date - timedelta(days=self.product.alert_time)

        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())

    @freeze_time("2025-01-01")
    def test_match_standard_and_auto_calculate(self):
        """Checks if auto calculations matches standard Odoo behavior"""
        lot_std = self.env["stock.lot"].create(
            {"name": "std", "product_id": self.product.id}
        )
        lot_julian = self.env["stock.lot"].create(
            {"name": "25001", "product_id": self.product.id}
        )

        self.assertEqual(
            lot_std.expiration_date.date(), lot_julian.expiration_date.date()
        )
        self.assertEqual(lot_std.use_date.date(), lot_julian.use_date.date())
        self.assertEqual(lot_std.removal_date.date(), lot_julian.removal_date.date())
        self.assertEqual(lot_std.alert_date.date(), lot_julian.alert_date.date())
