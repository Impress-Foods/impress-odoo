from odoo.exceptions import ValidationError

from ..tools import string_formatter
from .test_common import TestCommon


class TestPrintField(TestCommon):
    """Field resolution: what a mapping points at, and what it reads."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.main_company").currency_id = cls.env.ref("base.USD")

    def test_get_direct_field_type_valid(self):
        _, mapping = self.make_single_field_report("res.company", "name")
        self.assertEqual(mapping.field_type, "char")

    def test_get_direct_field_type_wrong_field(self):
        """A mapping may not be saved pointing at a field that is not there.

        Asserted at write time on purpose.  Validation that only happens when
        ``field_type`` is read leaves a broken mapping sitting in the database
        and turns the profile form into the thing that raises, so the mapping
        that needs fixing is on the record that can no longer be opened.
        """
        with self.assertRaises(ValidationError):
            self.make_single_field_report("res.company", "names")

    def test_get_chained_field_type(self):
        _, mapping = self.make_single_field_report("res.company", "currency_id.name")
        self.assertEqual(mapping.field_type, "char")

    def test_get_chained_field_value(self):
        _, mapping = self.make_single_field_report("res.company", "currency_id.name")
        company = self.env.ref("base.main_company")
        value = mapping.get_value(company)
        self.assertEqual(value, self.env.ref("base.USD").name)

    def test_get_translated_field(self):
        name_fr = "French Name"
        name_en = "English Name"

        report, _ = self.make_single_field_report("res.country", "name", translate=True)
        country = self.make_translated_country(name_en, name_fr)

        values = report._render_json_payload(country)

        self.assertIn("field_fr", values)
        self.assertEqual(values["field_fr"], name_fr)
        self.assertIn("field_en", values)
        self.assertEqual(values["field_en"], name_en)

    def test_target_field_underscore_raises(self):
        with self.assertRaises(ValidationError):
            self.make_single_field_report("res.company", "name", "_private")

    def test_chained_non_relational_raises(self):
        """``name.foo`` cannot be walked: ``name`` is not relational.

        Rejected at write time for the same reason as the missing-field case
        above.
        """
        with self.assertRaises(ValidationError):
            self.make_single_field_report("res.company", "name.foo")

    def test_static_value_type_and_value(self):
        _, mapping = self.make_single_field_report("res.company", "name")
        mapping.write({"source_field": False, "static_value": "  hello  "})
        self.assertEqual(mapping.field_type, "char")
        self.assertEqual(mapping.get_value(), "  hello  ")
        self.assertEqual(
            mapping.get_formatted_value(self.env.ref("base.main_company")),
            "hello",
        )

    def test_get_value_missing_source_raises(self):
        _, mapping = self.make_single_field_report("res.company", "name")
        mapping.write({"source_field": False})
        with self.assertRaises(ValidationError):
            mapping.get_value(self.env.ref("base.main_company"))

    def test_get_formatted_many2one_uses_display_name(self):
        _, mapping = self.make_single_field_report("res.company", "currency_id")
        company = self.env.ref("base.main_company")
        self.assertEqual(
            mapping.get_formatted_value(company), company.currency_id.display_name
        )

    def test_get_formatted_datetime(self):
        _, mapping = self.make_single_field_report("res.country", "create_date")
        mapping.write({"formatting": "%Y-%m-%d"})
        country = self.make_translated_country("dt en", "dt fr")
        expected = country.create_date.strftime("%Y-%m-%d")
        self.assertEqual(mapping.get_formatted_value(country), expected)

    def test_get_formatted_int_passthrough(self):
        _, mapping = self.make_single_field_report("res.country", "id")
        country = self.make_translated_country("int en", "int fr")
        self.assertEqual(mapping.get_formatted_value(country), country.id)

    def test_formatting_help_lists_every_transform(self):
        """The help text must name every transform the formatter will run.

        Keeps the field's tooltip and ``STRING_TRANSFORMS`` from drifting apart.
        """
        help_text = self.env["print.field"].fields_get(["formatting"])["formatting"][
            "help"
        ]
        for name in string_formatter.STRING_TRANSFORMS:
            self.assertIn(name, help_text)
