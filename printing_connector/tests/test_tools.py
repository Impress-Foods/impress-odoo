from datetime import datetime, timezone

from odoo.tests import TransactionCase

from ..tools import date_formatter, string_formatter


class TestTools(TransactionCase):
    def test_format_date_isoformat(self):
        date_obj = datetime(2026, 1, 15, 10, 30, 5, tzinfo=timezone.utc)
        self.assertEqual(
            date_formatter.format_date(date_obj),
            date_obj.isoformat(timespec="seconds"),
        )

    def test_format_date_strftime(self):
        date_obj = datetime(2026, 3, 5, 8, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(
            date_formatter.format_date(date_obj, "%Y-%m-%d"),
            "2026-03-05",
        )

    def test_format_date_custom_month_code(self):
        date_obj = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.assertEqual(date_formatter.format_date(date_obj, "%q"), "JA")
        date_obj = datetime(2026, 12, 10, tzinfo=timezone.utc)
        self.assertEqual(
            date_formatter.format_date(date_obj, "prefix-%q-suffix"),
            "prefix-DE-suffix",
        )

    def test_format_string_strips(self):
        self.assertEqual(string_formatter.format_string("  hello  ", None), "hello")

    def test_format_string_passthrough(self):
        self.assertEqual(string_formatter.format_string("hello", None), "hello")
        self.assertEqual(
            string_formatter.format_string("  hello  ", "ignored"), "hello"
        )
