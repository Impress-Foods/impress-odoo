from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestCommon(TransactionCase):
    """Shared fixtures for the payload-profile tests.

    Every model used here comes from ``base`` on purpose.  This module depends
    only on ``base_report_to_printer`` and ``printing_label_format``, so
    ``product`` is not guaranteed to be installed in the database the tests run
    against, and a fixture that reaches for ``product.product`` would pass on a
    developer's machine and fail in CI.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lang_model = cls.env["res.lang"]
        # The lang rows ship with ``base`` but are inactive, and an inactive
        # language is not translated for, so the fixtures activate what they use.
        cls.fr = lang_model.search(
            [("code", "=", "fr_CA"), ("active", "in", [False, True])]
        )
        cls.fr.active = True
        cls.en = lang_model.search([("code", "=", "en_US")])
        # ``res_country.code`` is unique and the country fixture needs one.
        cls._country_seq = 0

    @classmethod
    def make_single_field_report(
        cls,
        model: str,
        mapping: str,
        mapping_target: str = "field",
        translate: bool = False,
    ):
        """Return a ``print.report`` with one mapping, and that mapping.

        ``mapping`` is written as the source path so a test can spell a chained
        path (``"currency_id.name"``) or a deliberately broken one
        (``"name.foo"``) and still build the profile the same way.
        """
        report = cls.env["print.report"].create(
            {
                "name": "test",
                "template": "test",
                "target_model_id": cls.env["ir.model"]
                .search([("model", "=", model)], limit=1)
                .id,
            }
        )
        mapping_values = {
            "source_field": mapping,
            "target_field": mapping_target,
        }
        if translate:
            mapping_values["translate"] = True
            mapping_values["languages"] = [Command.set([cls.fr.id, cls.en.id])]

        report.write({"mapping_ids": [Command.create(mapping_values)]})
        return report, report.mapping_ids[0]

    @classmethod
    def make_translated_country(cls, english_name: str, french_name: str):
        """Return a country whose name carries both translations.

        A translatable field is what the ``translate`` mapping option is for, so
        the fixture needs one on a ``base`` model.  ``res.country.name`` is such
        a field: Odoo 19 dropped ``translate`` from ``res.partner.name``, so the
        obvious partner fixture stores a single value and every translated
        assertion would end up comparing a string against itself.  French has to
        be active for its translations to be read back, which is why
        ``setUpClass`` activates it.
        """
        cls._country_seq += 1
        country = cls.env["res.country"].create(
            {"name": english_name, "code": f"Z{cls._country_seq}"}
        )
        country.with_context(lang=cls.fr.code).write({"name": french_name})
        return country
