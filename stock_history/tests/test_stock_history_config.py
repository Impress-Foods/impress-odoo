from datetime import date

from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestStockHistoryConfig(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StockHistoryConfig = cls.env["stock.history.config"]
        cls.today = date(2025, 6, 15)  # A Sunday

    def create_config(self, **kwargs):
        """Helper to create a stock history config with default values"""
        defaults = {
            "name": "Test Config",
            "interval_type": "days",
            "duration": 1,
        }
        defaults.update(kwargs)
        return self.StockHistoryConfig.create(defaults)

    @freeze_time("2025-06-15")
    def test_next_run_days(self):
        # Test basic day interval
        config = self.create_config(interval_type="days", duration=1)
        self.assertEqual(config.next_run, date(2025, 6, 16))

        # Test multiple days
        config = self.create_config(interval_type="days", duration=5)
        self.assertEqual(config.next_run, date(2025, 6, 20))

        # Test with last_run set
        config = self.create_config(
            interval_type="days", duration=1, last_run=date(2025, 6, 10)
        )
        self.assertEqual(config.next_run, date(2025, 6, 11))

    @freeze_time("2025-06-15")
    def test_next_run_weeks(self):
        # Test basic week interval
        config = self.create_config(interval_type="weeks", duration=1)
        self.assertEqual(config.next_run, date(2025, 6, 22))

        # Test multiple weeks
        config = self.create_config(interval_type="weeks", duration=2)
        self.assertEqual(config.next_run, date(2025, 6, 29))

    @freeze_time("2025-06-15")
    def test_next_run_months(self):
        # Test basic month interval
        config = self.create_config(interval_type="months", duration=1)
        self.assertEqual(config.next_run, date(2025, 7, 15))

        # Test month end handling (July has 31 days, August has 31)
        with freeze_time("2025-01-31"):
            config = self.create_config(interval_type="months", duration=1)
            self.assertEqual(config.next_run, date(2025, 2, 28))  # Not a leap year

    @freeze_time("2025-06-15")
    def test_next_run_years(self):
        # Test basic year interval
        config = self.create_config(interval_type="years", duration=1)
        self.assertEqual(config.next_run, date(2026, 6, 15))

        # Test leap year handling
        with freeze_time("2024-02-29"):  # Leap day
            config = self.create_config(interval_type="years", duration=1)
            self.assertEqual(config.next_run, date(2025, 2, 28))  # Not a leap year

    # Sunday
    def test_next_run_day_of_week(self):
        with freeze_time("2025-06-15"):
            # Test next Monday
            config = self.create_config(interval_type="day_of_week", day_of_week="mon")
            self.assertEqual(config.next_run, date(2025, 6, 16))

            # Test next Wednesday
            config = self.create_config(interval_type="day_of_week", day_of_week="wed")
            self.assertEqual(config.next_run, date(2025, 6, 18))

            # Test next Sunday (should be next week)
            config = self.create_config(interval_type="day_of_week", day_of_week="sun")
            self.assertEqual(config.next_run, date(2025, 6, 22))

        with freeze_time("2025-12-28"):
            # Test next Sunday (should be next week)
            config = self.create_config(interval_type="day_of_week", day_of_week="thu")
            self.assertEqual(config.next_run, date(2026, 1, 1))

    def test_next_run_day_of_month(self):
        with freeze_time("2025-06-15"):
            # Test day later in current month
            config = self.create_config(interval_type="day_of_month", day_of_month=20)
            self.assertEqual(config.next_run, date(2025, 6, 20))

            # Test day in next month (15th is past the 10th)
            config = self.create_config(interval_type="day_of_month", day_of_month=10)
            self.assertEqual(config.next_run, date(2025, 7, 10))

            # Test with last_run set
            config = self.create_config(
                interval_type="day_of_month", day_of_month=10, last_run=date(2025, 5, 1)
            )
            self.assertEqual(config.next_run, date(2025, 5, 10))

        with freeze_time("2025-12-20"):
            config = self.create_config(
                interval_type="day_of_month",
                day_of_month=15,
                last_run=date(2025, 12, 15),
            )
            self.assertEqual(config.next_run, date(2026, 1, 15))

    @freeze_time("2025-06-15")  # June 15, 2025
    def test_next_run_day_of_year(self):
        # Test day of year in current year (after current date)
        config = self.create_config(
            interval_type="day_of_year",
            month_of_year="jul",
            day_of_month=15,  # July 15
        )
        self.assertEqual(config.next_run, date(2025, 7, 15))

        # Test day of year in next year (before current date)
        config = self.create_config(
            interval_type="day_of_year",
            month_of_year="may",
            day_of_month=1,  # May 1
        )
        self.assertEqual(config.next_run, date(2026, 5, 1))

        # Test with last_run set to a specific date
        config = self.create_config(
            interval_type="day_of_year",
            month_of_year="dec",
            day_of_month=25,  # December 25
            last_run=date(2024, 12, 25),
        )
        self.assertEqual(config.next_run, date(2025, 12, 25))

        # Test month with fewer days than selected day (April 31st doesn't exist)
        with self.assertRaises(ValidationError):
            self.create_config(
                interval_type="day_of_year",
                month_of_year="apr",
                day_of_month=31,  # April only has 30 days
                last_run=date(2024, 4, 30),
            )

    def test_day_of_year_validation(self):
        # Test valid day of year
        self.create_config(
            interval_type="day_of_year", month_of_year="feb", day_of_month=15
        )

        # Test invalid day for February (non-leap year)
        with self.assertRaises(ValidationError):
            self.create_config(
                interval_type="day_of_year", month_of_year="feb", day_of_month=29
            )

        # Test invalid day for April
        with self.assertRaises(ValidationError):
            self.create_config(
                interval_type="day_of_year", month_of_year="apr", day_of_month=31
            )
        with self.assertRaises(ValidationError):
            self.create_config(
                interval_type="day_of_year", month_of_year="dec", day_of_month=32
            )

    def test_next_run_end_of_month(self):
        # Test end of current month
        with freeze_time("2025-06-15"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2025, 6, 30))

        # Test end of next month
        with freeze_time("2025-03-31"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2025, 4, 30))

        # Test February in non-leap year
        with freeze_time("2025-02-15"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2025, 2, 28))

        with freeze_time("2024-12-15"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2024, 12, 31))

        # Test February in leap year
        with freeze_time("2028-02-15"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2028, 2, 29))

    def test_day_of_month_validation(self):
        # Test valid day of month
        self.create_config(interval_type="day_of_month", day_of_month=15)

        # Test invalid day of month
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=-1)
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=0)
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=29)
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=30)
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=31)

    def test_product_filtering_and_history_creation(self):
        """Test product filtering and history creation"""
        # Create test products
        uom_unit = self.env.ref("uom.product_uom_unit")
        category = self.env["product.category"].create({"name": "Test Category"})

        # Create products with different categories and types
        product1 = self.env["product.product"].create(
            {
                "name": "Test Product 1",
                "type": "product",
                "categ_id": category.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
            }
        )

        self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "product",
                "categ_id": category.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
            }
        )

        # Create a service product that should be filtered out
        self.env["product.product"].create(
            {
                "name": "Service Product",
                "type": "service",
                "categ_id": category.id,
            }
        )

        # Create stock for the products
        self.env["stock.quant"].create(
            {
                "product_id": product1.id,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
                "quantity": 10,
            }
        )

        # Create a config with a domain to filter only product1
        domain = f"[('id', '=', {product1.id})]"
        with freeze_time("2025-06-15"):
            config = self.create_config(
                interval_type="days", duration=1, product_domain=domain
            )

            # Test _get_products
            products = config._get_products()
            self.assertEqual(len(products), 1)
            self.assertEqual(products, product1)

            # Test _get_quants
            quants = config._get_quants()
            self.assertEqual(len(quants), 1)
            self.assertEqual(quants.product_id, product1)
            self.assertEqual(quants.quantity, 10)

            # Test _create_history
            config._create_history()

            # Verify history group was created
            history_group = self.env["stock.history.group"].search(
                [], order="id desc", limit=1
            )
            self.assertTrue(history_group)
            self.assertEqual(history_group.history_config_id, config)
            self.assertEqual(history_group.date, date(2025, 6, 15))
            self.assertIn(config.name, history_group.name)

            # Verify history lines were created
            history_lines = history_group.history_line_ids
            self.assertEqual(len(history_lines), 1)
            self.assertEqual(history_lines.product_id, product1)
            self.assertEqual(history_lines.quantity, 10)
            self.assertEqual(
                history_lines.location,
                self.env.ref("stock.stock_location_stock"),  # type: ignore
            )
            self.assertEqual(history_lines.uom, uom_unit)

            # Verify sequence was generated
            self.assertNotEqual(history_lines.sequence, "New")

    def test_product_filtering_and_history_creation_with_lot(self):
        """Test product filtering and history creation"""
        # Create test products
        uom_unit = self.env.ref("uom.product_uom_unit")
        category = self.env["product.category"].create({"name": "Test Category"})

        # Create products with different categories and types
        product1 = self.env["product.product"].create(
            {
                "name": "Test Product 1",
                "type": "product",
                "categ_id": category.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
                "tracking": "lot",
            }
        )

        self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "product",
                "categ_id": category.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
                "tracking": "lot",
            }
        )

        # Create a service product that should be filtered out
        self.env["product.product"].create(
            {
                "name": "Service Product",
                "type": "service",
                "categ_id": category.id,
            }
        )

        lot_1 = self.env["stock.lot"].create(
            {"name": "test_lot_1", "product_id": product1.id}
        )

        # Create stock for the products
        self.env["stock.quant"].create(
            {
                "product_id": product1.id,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
                "quantity": 10,
                "lot_id": lot_1.id,
            }
        )

        # Create a config with a domain to filter only product1
        domain = f"[('id', '=', {product1.id})]"
        with freeze_time("2025-06-15"):
            config = self.create_config(
                interval_type="days", duration=1, product_domain=domain
            )

            # Test _get_products
            products = config._get_products()
            self.assertEqual(len(products), 1)
            self.assertEqual(products, product1)

            # Test _get_quants
            quants = config._get_quants()
            self.assertEqual(len(quants), 1)
            self.assertEqual(quants.product_id, product1)
            self.assertEqual(quants.quantity, 10)

            # Test _create_history
            config._create_history()

            # Verify history group was created
            history_group = self.env["stock.history.group"].search(
                [], order="id desc", limit=1
            )
            self.assertTrue(history_group)
            self.assertEqual(history_group.history_config_id, config)
            self.assertEqual(history_group.date, date(2025, 6, 15))
            self.assertIn(config.name, history_group.name)

            # Verify history lines were created
            history_lines = history_group.history_line_ids
            self.assertEqual(len(history_lines), 1)
            self.assertEqual(history_lines.product_id, product1)
            self.assertEqual(history_lines.quantity, 10)
            self.assertEqual(history_lines.lot_id.id, lot_1.id)
            self.assertEqual(
                history_lines.location,
                self.env.ref("stock.stock_location_stock"),  # type: ignore
            )
            self.assertEqual(history_lines.uom, uom_unit)

            # Verify sequence was generated
            self.assertNotEqual(history_lines.sequence, "New")

    def test_cron_create_history(self):
        """Test the cron job that creates history entries"""
        # Create a product and stock
        product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
            }
        )
        stock_location = self.env.ref("stock.stock_location_stock")  # type: ignore
        self.env["stock.quant"].create(
            {
                "product_id": product.id,
                "location_id": stock_location.id,  # type: ignore
                "quantity": 15,
            }
        )

        # Create a config with next_run in the past
        with freeze_time("2025-06-14"):
            past_config = self.create_config(
                interval_type="days",
                duration=1,
                product_domain=f"[('id', '=', {product.id})]",
            )
            past_config.next_run = date(2025, 6, 14)  # Set to yesterday

        # Create a config with next_run in the future
        future_config = self.create_config(
            interval_type="days",
            duration=1,
            product_domain=f"[('id', '=', {product.id})]",
            next_run=date(2025, 6, 16),  # Set to tomorrow
        )

        # Run the cron with today's date
        with freeze_time("2025-06-15"):
            self.StockHistoryConfig.cron_create_history()

            # Verify only the past config was processed
            self.assertTrue(past_config.last_run)
            self.assertEqual(past_config.last_run, date(2025, 6, 15))
            self.assertEqual(past_config.next_run, date(2025, 6, 16))

            # Future config should not have been processed
            self.assertFalse(future_config.last_run)
            self.assertEqual(future_config.next_run, date(2025, 6, 16))

            # Verify history group and lines were created for past_config
            history_group = self.env["stock.history.group"].search(
                [("history_config_id", "=", past_config.id)], limit=1
            )
            self.assertTrue(history_group)
            self.assertEqual(len(history_group.history_line_ids), 1)
            self.assertEqual(history_group.history_line_ids.quantity, 15)

    def test_end_of_month_validation(self):
        # Create a config with end of month
        config = self.create_config(interval_type="end_of_month")

        # Try to set next_run to a non-end-of-month date
        with self.assertRaises(ValidationError):
            config.next_run = date(2025, 6, 15)
