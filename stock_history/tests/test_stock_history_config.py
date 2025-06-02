from datetime import date

from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
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

    @freeze_time("2025-06-15")  # Sunday
    def test_next_run_day_of_week(self):
        # Test next Monday
        config = self.create_config(interval_type="day_of_week", day_of_week="mon")
        self.assertEqual(config.next_run, date(2025, 6, 16))

        # Test next Wednesday
        config = self.create_config(interval_type="day_of_week", day_of_week="wed")
        self.assertEqual(config.next_run, date(2025, 6, 18))

        # Test next Sunday (should be next week)
        config = self.create_config(interval_type="day_of_week", day_of_week="sun")
        self.assertEqual(config.next_run, date(2025, 6, 22))

    @freeze_time("2025-06-15")
    def test_next_run_day_of_month(self):
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

        # Test February in leap year
        with freeze_time("2028-02-15"):
            config = self.create_config(interval_type="end_of_month")
            self.assertEqual(config.next_run, date(2028, 2, 29))

    def test_day_of_month_validation(self):
        # Test valid day of month
        self.create_config(interval_type="day_of_month", day_of_month=15)

        # Test invalid day of month
        with self.assertRaises(ValidationError):
            self.create_config(interval_type="day_of_month", day_of_month=29)

    def test_end_of_month_validation(self):
        # Create a config with end of month
        config = self.create_config(interval_type="end_of_month")

        # Try to set next_run to a non-end-of-month date
        with self.assertRaises(ValidationError):
            config.next_run = date(2025, 6, 15)
