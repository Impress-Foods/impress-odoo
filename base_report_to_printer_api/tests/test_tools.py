from datetime import date, datetime, timezone

from odoo.tests.common import TransactionCase

from ..tools import date_formatter, string_formatter


class TestPrintingApiTools(TransactionCase):
    def test_date_defaults_to_isoformat(self):
        value = datetime(2026, 1, 15, 10, 30, 5, tzinfo=timezone.utc)
        self.assertEqual(
            date_formatter.format_date(value),
            value.isoformat(timespec="seconds"),
        )
        self.assertEqual(date_formatter.format_date(date(2026, 1, 15)), "2026-01-15")

    def test_date_supports_custom_month_abbreviation(self):
        value = date(2026, 12, 10)
        self.assertEqual(date_formatter.format_date(value, "%q"), "DE")
        self.assertEqual(
            date_formatter.format_date(value, "prefix-%q-suffix"),
            "prefix-DE-suffix",
        )

    def test_string_formatter_strips_whitespace(self):
        self.assertEqual(string_formatter.format_string("  value  "), "value")
