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

    def test_string_formatter_ignores_its_format_argument(self):
        """Pins the gap: ``formatting`` reaches string mappings but is unused.

        The ``formatting`` field is offered on every mapping in the profile form
        and does reach this function, but the string path only strips.  Dates do
        honour it via ``strftime``, so a profile that configures ``formatting``
        on a string mapping currently gets nothing back.  This test documents
        the behaviour as it stands; it is the tripwire for either implementing
        string formatting or dropping the field from the string case.
        """
        self.assertEqual(string_formatter.format_string("  hello  ", None), "hello")
        self.assertEqual(string_formatter.format_string("hello", None), "hello")
        self.assertEqual(
            string_formatter.format_string("  hello  ", "ignored"), "hello"
        )
