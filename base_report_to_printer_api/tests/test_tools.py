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

    def test_date_uses_strftime_when_formatting_is_set(self):
        value = datetime(2026, 3, 5, 8, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(
            date_formatter.format_date(value, "%Y-%m-%d"),
            "2026-03-05",
        )

    def test_date_supports_custom_month_abbreviation(self):
        value = date(2026, 12, 10)
        self.assertEqual(date_formatter.format_date(value, "%q"), "DE")
        self.assertEqual(
            date_formatter.format_date(value, "prefix-%q-suffix"),
            "prefix-DE-suffix",
        )

    def test_string_formatter_strips_whitespace(self):
        self.assertEqual(string_formatter.format_string("  value  "), "value")

    def test_string_formatter_leaves_a_clean_value_alone(self):
        self.assertEqual(string_formatter.format_string("value"), "value")

    def test_string_formatter_applies_a_named_transform(self):
        self.assertEqual(string_formatter.format_string("  Value  ", "lower"), "value")
        self.assertEqual(string_formatter.format_string("Value", "upper"), "VALUE")

    def test_string_formatter_applies_transforms_in_order(self):
        self.assertEqual(
            string_formatter.format_string("  hello world  ", "title"),
            "Hello World",
        )
        # The later transform sees the earlier one's output.
        self.assertEqual(
            string_formatter.format_string("  hello world  ", "title,upper"),
            "HELLO WORLD",
        )

    def test_string_formatter_skips_an_unknown_transform(self):
        """A bad option must not stop a print job.

        An unrecognised name is ignored, so the mapping still prints, just
        without the intended transformation.  A known name beside it still runs.
        """
        self.assertEqual(
            string_formatter.format_string("  hello  ", "uppercase"), "hello"
        )
        self.assertEqual(
            string_formatter.format_string("  hello  ", "uppercase,upper"), "HELLO"
        )
