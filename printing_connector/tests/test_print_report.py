from .test_common import TestCommon


class TestPrintReport(TestCommon):
    def test_render_json_payload(self):
        """Tests mappings + extra data merged"""
        name_en = "name english"
        name_fr = "name french"
        extra_data = {"extra": "data"}

        expected = {
            "name_fr": name_fr,
            "name_en": name_en,
            "extra": "data",
        }

        product = self.make_translated_product(name_en, name_fr)

        report, _ = self.make_single_field_report(
            "product.product", "name", "name", translate=True
        )

        result = report._render_json_payload(product, extra_data=extra_data)
        self.assertDictEqual(result, expected)

    def test_render_json_payload_overwrite(self):
        """Tests if report mappings overwrites extra_data"""
        name_en = "name english"
        name_fr = "name french"
        extra_data = {"name_fr": "wrong_name"}

        expected = {
            "name_fr": name_fr,
            "name_en": name_en,
        }
        product = self.make_translated_product(name_en, name_fr)

        report, _ = self.make_single_field_report(
            "product.product", "name", "name", translate=True
        )

        result = report._render_json_payload(product, extra_data=extra_data)
        self.assertDictEqual(result, expected)

    def test_render_empty_mappings(self):
        """Empty mapping_ids renders only extra_data"""
        product = self.make_translated_product("en", "fr")
        report, mapping = self.make_single_field_report("product.product", "name")
        mapping.unlink()
        self.assertDictEqual(
            report._render_json_payload(product),
            {},
        )
        self.assertDictEqual(
            report._render_json_payload(product, extra_data={"a": "b"}),
            {"a": "b"},
        )

    def test_render_non_translated_only(self):
        """Non-translate mapping uses target_field as-is"""
        product = self.make_translated_product("plain en", "plain fr")
        report, _ = self.make_single_field_report("product.product", "name", "label")
        result = report._render_json_payload(product)
        self.assertDictEqual(result, {"label": "plain en"})

    def test_render_translate_no_languages_skipped(self):
        """Translate=True with no languages contributes nothing"""
        product = self.make_translated_product("en", "fr")
        report, mapping = self.make_single_field_report(
            "product.product", "name", "name"
        )
        mapping.write({"translate": True})
        self.assertDictEqual(report._render_json_payload(product), {})
