import logging

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase

_logger = logging.getLogger(__name__)


class TestPrintField(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.field_model = cls.env["print.field"]
        cls.report_model = cls.env["print.report"]

    def make_single_field_report(self, model, mapping):
        report = self.report_model.create(
            {
                "target_model_id": self.env["ir.model"]
                .search([("model", "=", model)], limit=1)[0]
                .id,
                "name": "test",
                "template": "test",
                "mapping_ids": [
                    Command.create(
                        {
                            "source_field": mapping,
                            "target_field": "field",
                        }
                    )
                ],
            }
        )
        return report, report.mapping_ids[0]

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
        company = self.env["res.company"].search([])[0]
        value = mapping.get_value(company)
        self.assertEqual(value, "USD")

    def test_get_translated_field(self):
        NAME_FR = "French Name"
        NAME_EN = "English Name"
        lang_model = self.env["res.lang"]
        fr = lang_model.search(
            [("code", "=", "fr_CA"), ("active", "in", [False, True])]
        )

        fr.active = True
        en = lang_model.search(
            [("code", "=", "en_US"), ("active", "in", [False, True])]
        )

        report, mapping = self.make_single_field_report("product.template", "name")

        mapping.translate = True
        mapping.languages = [fr.id, en.id]

        product = self.env["product.product"].create({"type": "consu", "name": NAME_EN})
        product.with_context(lang=fr.code).write({"name": NAME_FR})

        values = report._render_json_payload(product)

        self.assertIn("field_fr", values)
        self.assertEqual(values["field_fr"], NAME_FR)
        self.assertIn("field_en", values)
        self.assertEqual(values["field_en"], NAME_EN)
