from odoo.fields import Command
from odoo.tests import TransactionCase


class TestCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.field_model = cls.env["print.field"]
        cls.report_model = cls.env["print.report"]
        cls.product_model_rec = cls.env.ref("product.model_product_product")
        lang_model = cls.env["res.lang"]

        cls.fr = lang_model.search(
            [("code", "=", "fr_CA"), ("active", "in", [False, True])]
        )

        cls.fr.active = True
        cls.en = lang_model.search(
            [("code", "=", "en_US"), ("active", "in", [False, True])]
        )

    @classmethod
    def make_single_field_report(
        cls,
        model: str,
        mapping: str,
        mapping_target: str = "field",
        translate: bool = False,
    ):
        report = cls.report_model.create(
            {
                "target_model_id": cls.env["ir.model"]
                .search([("model", "=", model)], limit=1)
                .id,
                "name": "test",
                "template": "test",
            }
        )

        mapping_values = {
            "source_field": mapping,
            "target_field": mapping_target,
        }

        if translate:
            mapping_values["translate"] = True
            mapping_values["languages"] = [Command.set([cls.fr.id, cls.en.id])]

        report.write(
            {
                "mapping_ids": [Command.create(mapping_values)],
            }
        )
        return report, report.mapping_ids[0]

    @classmethod
    def make_translated_product(cls, english_name: str, french_name: str):
        product = cls.env["product.product"].create(
            {"type": "consu", "name": english_name}
        )
        product.with_context(lang=cls.fr.code).write({"name": french_name})
        return product
