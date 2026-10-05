from odoo.exceptions import ValidationError

from .test_common import TestCommon


class TestPrintReport(TestCommon):
    """Payload assembly: how mappings, translations and extra data combine.

    The profile resolves mappings into a flat payload and merges whatever the
    print action supplied.  Nothing here is aware of Seagull's reserved keys:
    ``_qty`` is the transport's spelling of the dashboard's ``label_count`` and
    is added when the request is built, not here.
    """

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

        country = self.make_translated_country(name_en, name_fr)

        report, _ = self.make_single_field_report(
            "res.country", "name", "name", translate=True
        )

        result = report._render_json_payload(country, extra_data=extra_data)
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
        country = self.make_translated_country(name_en, name_fr)

        report, _ = self.make_single_field_report(
            "res.country", "name", "name", translate=True
        )

        result = report._render_json_payload(country, extra_data=extra_data)
        self.assertDictEqual(result, expected)

    def test_render_empty_mappings(self):
        """Empty mapping_ids renders only extra_data"""
        country = self.make_translated_country("en", "fr")
        report, mapping = self.make_single_field_report("res.country", "name")
        mapping.unlink()
        self.assertDictEqual(report._render_json_payload(country), {})
        self.assertDictEqual(
            report._render_json_payload(country, extra_data={"a": "b"}),
            {"a": "b"},
        )

    def test_render_non_translated_only(self):
        """Non-translate mapping uses target_field as-is"""
        country = self.make_translated_country("plain en", "plain fr")
        report, _ = self.make_single_field_report("res.country", "name", "label")
        result = report._render_json_payload(country)
        self.assertDictEqual(result, {"label": "plain en"})

    def test_render_translate_no_languages_skipped(self):
        """Translate=True with no languages contributes nothing"""
        country = self.make_translated_country("en", "fr")
        report, mapping = self.make_single_field_report("res.country", "name", "name")
        mapping.write({"translate": True})
        self.assertDictEqual(report._render_json_payload(country), {})

    def test_repointing_the_profile_revalidates_its_mappings(self):
        """A mapping is checked again when its profile changes model.

        ``print.field`` is not written by a change to its profile, so the
        mapping's own constraint cannot run.  Without this the profile would
        keep a path that only resolved against the model it used to name --
        ``phone_code`` exists on a country and on nothing else.
        """
        report, _ = self.make_single_field_report("res.country", "phone_code")
        other_model = self.env["ir.model"].search([("model", "=", "res.partner")])

        with self.assertRaises(ValidationError):
            report.write({"target_model_id": other_model.id})

    def test_repointing_the_profile_keeps_mappings_that_still_resolve(self):
        """A path that resolves on both models is left alone."""
        report, _ = self.make_single_field_report("res.company", "display_name")
        other_model = self.env["ir.model"].search([("model", "=", "res.users")])

        report.write({"target_model_id": other_model.id})

        self.assertEqual(report.mapping_ids.field_type, "char")


class TestGetRecordData(TestCommon):
    """Which keys of the print action's ``data`` reach one record's payload.

    A multi-record job is sent as one request per record, so ``data`` may hold
    a nested entry per record id alongside job-wide keys.  Only the record's own
    entry and the job-wide keys belong in its payload.
    """

    def test_record_entry_is_merged_with_the_global_keys(self):
        report, _ = self.make_single_field_report("res.country", "name")
        first = self.make_translated_country("first", "premier")
        second = self.make_translated_country("second", "deuxieme")
        data = {"label_count": 2, str(first.id): {"lot": "A"}}

        self.assertDictEqual(
            report._get_record_data(data, first),
            {"label_count": 2, "lot": "A"},
        )
        # The sibling's entry is not part of this record's payload.
        self.assertDictEqual(
            report._get_record_data(
                {str(first.id): {"lot": "A"}, str(second.id): {"lot": "B"}}, second
            ),
            {"lot": "B"},
        )

    def test_a_record_without_an_entry_keeps_only_the_global_keys(self):
        """The regression: a missing entry used to return ``data`` verbatim.

        Returning the whole dict shipped every sibling record's entry as a
        literal field, keyed by a database id the label server cannot read.
        """
        report, _ = self.make_single_field_report("res.country", "name")
        first = self.make_translated_country("first", "premier")
        second = self.make_translated_country("second", "deuxieme")
        data = {"label_count": 2, str(first.id): {"lot": "A"}}

        self.assertDictEqual(
            report._get_record_data(data, second),
            {"label_count": 2},
        )

    def test_a_record_entry_may_be_keyed_by_integer_id(self):
        report, _ = self.make_single_field_report("res.country", "name")
        country = self.make_translated_country("first", "premier")

        self.assertDictEqual(
            report._get_record_data({country.id: {"lot": "A"}}, country),
            {"lot": "A"},
        )

    def test_no_data_yields_nothing(self):
        report, _ = self.make_single_field_report("res.country", "name")
        country = self.make_translated_country("first", "premier")

        self.assertDictEqual(report._get_record_data(None, country), {})
        self.assertDictEqual(report._get_record_data("not a dict", country), {})
