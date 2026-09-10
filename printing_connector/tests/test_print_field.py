from odoo.exceptions import ValidationError

from .test_common import TestCommon


class TestPrintField(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.main_company").currency_id = cls.env.ref("base.USD")

    def test_get_direct_field_type_valid(self):
        _, mapping = self.make_single_field_report("res.company", "name")
        self.assertEqual(mapping.field_type, "char")

    def test_get_direct_field_type_wrong_field(self):
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

        report, _ = self.make_single_field_report(
            "product.template", "name", translate=True
        )
        product = self.make_translated_product(name_en, name_fr)

        values = report._render_json_payload(product)

        self.assertIn("field_fr", values)
        self.assertEqual(values["field_fr"], name_fr)
        self.assertIn("field_en", values)
        self.assertEqual(values["field_en"], name_en)

    def test_target_field_underscore_raises(self):
        with self.assertRaises(ValidationError):
            self.make_single_field_report("res.company", "name", "_private")

    def test_chained_non_relational_raises(self):
        with self.assertRaises(ValidationError):
            self.make_single_field_report("res.company", "name.foo")

    def test_static_value_type_and_value(self):
        report, mapping = self.make_single_field_report("res.company", "name")
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
        _, mapping = self.make_single_field_report("product.product", "create_date")
        mapping.write({"formatting": "%Y-%m-%d"})
        product = self.make_translated_product("dt en", "dt fr")
        expected = product.create_date.strftime("%Y-%m-%d")
        self.assertEqual(mapping.get_formatted_value(product), expected)

    def test_get_formatted_int_passthrough(self):
        _, mapping = self.make_single_field_report("product.product", "id")
        product = self.make_translated_product("int en", "int fr")
        self.assertEqual(mapping.get_formatted_value(product), product.id)
