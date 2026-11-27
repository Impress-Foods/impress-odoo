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

        prod_date = date
        exp_date = date + timedelta(days=self.product.expiration_time)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time)
        alert_date = exp_date - timedelta(days=self.product.alert_time)

        self.assertEqual(lot.origin_date.date(), prod_date.date())
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

        prod_date = date
        exp_date = date + timedelta(days=self.product.expiration_time)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time)
        alert_date = exp_date - timedelta(days=self.product.alert_time)

        self.assertEqual(lot.origin_date.date(), prod_date.date())
        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())

    @freeze_time("2025-01-01")
    def test_invalid_lot_number_format(self):
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
    def test_invalid_lot_number_date(self):
        """Checks if invalid lot number uses default behavior"""
        date = datetime.today()
        lot = self.env["stock.lot"].create(
            {"name": "25367", "product_id": self.product.id}
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

        self.assertEqual(lot_std.origin_date.date(), lot_julian.origin_date.date())
        self.assertEqual(
            lot_std.expiration_date.date(), lot_julian.expiration_date.date()
        )
        self.assertEqual(lot_std.use_date.date(), lot_julian.use_date.date())
        self.assertEqual(lot_std.removal_date.date(), lot_julian.removal_date.date())
        self.assertEqual(lot_std.alert_date.date(), lot_julian.alert_date.date())

    def _assert_dates_from_production(self, lot, production: datetime):
        """Asserts every lot date was derived from the given production date."""
        exp_date = production + timedelta(days=self.product.expiration_time)
        self.assertEqual(lot.origin_date.date(), production.date())
        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(
            lot.use_date.date(),
            (exp_date - timedelta(days=self.product.use_time)).date(),
        )
        self.assertEqual(
            lot.removal_date.date(),
            (exp_date - timedelta(days=self.product.removal_time)).date(),
        )
        self.assertEqual(
            lot.alert_date.date(),
            (exp_date - timedelta(days=self.product.alert_time)).date(),
        )

    def test_name_create_with_default_product(self):
        """Quick-creating a lot from a many2one uses the context product"""
        lot_id, _name = (
            self.env["stock.lot"]
            .with_context(default_product_id=self.product.id)
            .name_create("25001")
        )
        lot = self.env["stock.lot"].browse(lot_id)

        self.assertEqual(lot.product_id, self.product)
        self._assert_dates_from_production(lot, datetime(2025, 1, 1))

    def test_create_with_default_product(self):
        """Dates are calculated when product_id only comes from the context"""
        lot = (
            self.env["stock.lot"]
            .with_context(default_product_id=self.product.id)
            .create({"name": "25032"})
        )

        self._assert_dates_from_production(lot, datetime(2025, 2, 1))

    @freeze_time("2025-03-01")
    def test_create_with_sequence_name(self):
        """Dates are calculated when the name comes from the lot sequence"""
        self.product.lot_sequence_id = self.env["ir.sequence"].create(
            {"name": "Julian lots", "prefix": "%(y)s%(doy)s-", "padding": 3}
        )
        lot = self.env["stock.lot"].create({"product_id": self.product.id})

        self.assertTrue(lot.name.startswith("25060-"))
        self._assert_dates_from_production(lot, datetime(2025, 3, 1))

    def test_create_multi_different_names(self):
        """Batch creation computes each lot from its own name"""
        lots = self.env["stock.lot"].create(
            [
                {"name": "25001", "product_id": self.product.id},
                {"name": "25032", "product_id": self.product.id},
                {"name": "25001-B", "product_id": self.product.id},
            ]
        )

        self._assert_dates_from_production(lots[0], datetime(2025, 1, 1))
        self._assert_dates_from_production(lots[1], datetime(2025, 2, 1))
        self._assert_dates_from_production(lots[2], datetime(2025, 1, 1))

    def test_create_keeps_explicit_origin_date(self):
        """An explicit origin_date is kept when the name cannot be parsed"""
        origin = datetime(2024, 6, 15, 12, 0)
        lot = self.env["stock.lot"].create(
            {"name": "std", "product_id": self.product.id, "origin_date": origin}
        )

        self.assertEqual(lot.origin_date, origin)

    def test_create_product_without_expiration(self):
        """Products without expiration dates are left untouched"""
        product = self.env["product.product"].create(
            {
                "name": "No Expiry Product",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
                "use_expiration_date": False,
            }
        )
        lot = self.env["stock.lot"].create({"name": "25001", "product_id": product.id})

        self.assertFalse(lot.expiration_date)
        self.assertFalse(lot.alert_date)

    def test_server_action_recalculates_dates(self):
        """The server action recomputes dates on every selected lot"""
        lots = self.env["stock.lot"].create(
            [
                {"name": "25001", "product_id": self.product.id},
                {"name": "25032", "product_id": self.product.id},
            ]
        )
        lots.write({"expiration_date": datetime(2030, 1, 1), "origin_date": False})

        action = self.env.ref(
            "impress_expiration_lot.impress_expiration_parse_lot_number_action"
        )
        action.with_context(
            active_model="stock.lot", active_ids=lots.ids, active_id=lots[0].id
        ).run()

        self._assert_dates_from_production(lots[0], datetime(2025, 1, 1))
        self._assert_dates_from_production(lots[1], datetime(2025, 2, 1))

    def test_calculate_on_empty_recordset(self):
        """Calculating on an empty recordset is a no-op"""
        self.env["stock.lot"]._calculate_expiration_date()
