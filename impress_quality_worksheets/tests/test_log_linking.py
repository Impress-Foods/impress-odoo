"""Characterization: how worksheets, logs, log lines and quality checks link today."""

from odoo.tests import tagged

from .common import LINE_LOG_FIELD, TEMPLATES, WorksheetCase

LINE_TEMPLATES = [key for key, spec in TEMPLATES.items() if spec[2]]


@tagged("post_install", "-at_install")
class TestWorksheetLogCreation(WorksheetCase):
    """The worksheet's stored compute on x_<type>_log_id finds or creates the log."""

    def test_worksheet_creates_log_named_after_production(self):
        for key, (_xmlid, log_field, _lines, log_model) in TEMPLATES.items():
            with self.subTest(template=key):
                production = self._create_production()
                check = self.create_check(key, production)

                worksheet = self.create_worksheet(key, check)

                log = worksheet[log_field]
                self.assertEqual(log._name, log_model)
                self.assertEqual(log.name, production.name)
                self.assertEqual(log.quality_check_id, check)
                self.assertEqual(log.production_id, production)
                self.assertEqual(log.product_id, self.product)

    def test_second_check_on_same_production_reuses_log(self):
        """One log per type per production: a second check finds the first log.

        The log keeps pointing at the first check that created it.
        """
        for key, (_xmlid, log_field, _lines, log_model) in TEMPLATES.items():
            with self.subTest(template=key):
                production = self._create_production()
                first_check = self.create_check(key, production)
                second_check = self.create_check(key, production)

                first = self.create_worksheet(key, first_check)
                second = self.create_worksheet(key, second_check)

                self.assertEqual(second[log_field], first[log_field])
                self.assertEqual(first[log_field].quality_check_id, first_check)
                self.assertEqual(
                    self.env[log_model].search_count([("name", "=", production.name)]),
                    1,
                )

    def test_template_versions_share_the_production_log(self):
        """A newer template version of the same type reuses the existing log."""
        production = self._create_production()
        old = self.create_worksheet(
            "metal_20250203", self.create_check("metal_20250203", production)
        )
        new = self.create_worksheet(
            "metal_large_20260303",
            self.create_check("metal_large_20260303", production),
        )
        self.assertEqual(new.x_metal_log_id, old.x_metal_log_id)

    def test_existing_log_with_production_name_is_reused(self):
        production = self._create_production()
        existing = self.env["hpp.log"].create({"name": production.name})

        worksheet = self.create_worksheet(
            "hpp_20250203", self.create_check("hpp_20250203", production)
        )

        self.assertEqual(worksheet.x_hpp_log_id, existing)
        # The reused log is not re-linked to the check.
        self.assertFalse(existing.quality_check_id)

    def test_checks_without_production_share_one_log(self):
        """Known exposure: the lookup matches on name, and False matches False.

        Every worksheet whose check has no production ends up on the same log.
        """
        checks = self.env["quality.check"].create(
            [
                {"point_id": self.points["hpp_20250203"].id},
                {"point_id": self.points["hpp_20250203"].id},
            ]
        )
        first = self.create_worksheet("hpp_20250203", checks[0])
        second = self.create_worksheet("hpp_20250203", checks[1])

        self.assertTrue(first.x_hpp_log_id)
        self.assertFalse(first.x_hpp_log_id.name)
        self.assertEqual(second.x_hpp_log_id, first.x_hpp_log_id)


@tagged("post_install", "-at_install")
class TestLogLineLinking(WorksheetCase):
    """Lines are created nested in the worksheet, through x_<type>_log_line_ids."""

    def test_lines_link_to_check_production_and_log(self):
        for key in LINE_TEMPLATES:
            _xmlid, log_field, lines_field, log_model = TEMPLATES[key]
            with self.subTest(template=key):
                production = self._create_production()
                check = self.create_check(key, production)

                worksheet = self.create_worksheet(
                    key, check, [self.line_vals(key, 1), self.line_vals(key, 2)]
                )

                lines = worksheet[lines_field]
                log = worksheet[log_field]
                self.assertEqual(len(lines), 2)
                self.assertEqual(lines.quality_check_id, check)
                self.assertEqual(lines.production_id, production)
                self.assertEqual(lines.product_id, self.product)
                self.assertEqual(lines[LINE_LOG_FIELD[log_model]], log)
                self.assertEqual(log.log_line_ids, lines)

    def test_active_worksheet_field_names_the_template_column(self):
        """Each template version has its own x_worksheet_* column on the line."""
        for key in LINE_TEMPLATES:
            _xmlid, _log_field, lines_field, _log_model = TEMPLATES[key]
            with self.subTest(template=key):
                worksheet = self.create_worksheet(
                    key, self.create_check(key), [self.line_vals(key, 100)]
                )
                line = worksheet[lines_field]
                ws_field = line.active_worksheet_field

                self.assertTrue(ws_field.startswith("x_worksheet_"))
                self.assertEqual(line[ws_field], worksheet)

    def test_lines_without_wizard_context_get_no_check(self):
        """Outside the wizard flow, lines are not linked to the check.

        They still reach the log, because the log comes from the worksheet.
        """
        for key in LINE_TEMPLATES:
            _xmlid, log_field, lines_field, log_model = TEMPLATES[key]
            with self.subTest(template=key):
                production = self._create_production()
                worksheet = self.create_worksheet(
                    key,
                    self.create_check(key, production),
                    [self.line_vals(key)],
                    use_wizard=False,
                )

                line = worksheet[lines_field]
                self.assertFalse(line.quality_check_id)
                self.assertFalse(line.production_id)
                self.assertEqual(line[LINE_LOG_FIELD[log_model]], worksheet[log_field])

    def test_line_created_from_log_line_list_is_not_linked(self):
        """Known gap: lines created from the log's "view lines" list are orphaned.

        action_view_hpp_lines passes default_hpp_log_id, but hpp_log_id is a
        read-only compute, so the default is ignored. The list allows "New".
        """
        worksheet = self.create_worksheet(
            "hpp_20250203", self.create_check("hpp_20250203")
        )
        log = worksheet.x_hpp_log_id

        line = (
            self.env["hpp.log.line"]
            .with_context(default_hpp_log_id=log.id)
            .create(self.line_vals("hpp_20250203", 7))
        )

        self.assertFalse(line.hpp_log_id)
        self.assertNotIn(line, log.log_line_ids)
        self.assertFalse(line.active_worksheet_field)
        self.assertFalse(line.quality_check_id)


@tagged("post_install", "-at_install")
class TestLotLinking(WorksheetCase):
    def test_lot_follows_production_lot(self):
        production = self._create_production()
        lot = self.env["stock.lot"].create(
            {"name": "LOT-CHAR-1", "product_id": self.product.id}
        )
        production.lot_producing_ids = lot

        worksheet = self.create_worksheet(
            "hpp_20250203",
            self.create_check("hpp_20250203", production),
            [self.line_vals("hpp_20250203")],
        )

        self.assertEqual(worksheet.x_hpp_log_id.lot_id, lot)
        self.assertEqual(worksheet.x_hpp_log_line_ids.product_lot_id, lot)

    def test_lot_change_on_production_updates_existing_log(self):
        """The log's lot is live: changing the MO lot rewrites past logs."""
        production = self._create_production()
        first_lot, second_lot = self.env["stock.lot"].create(
            [
                {"name": "LOT-CHAR-A", "product_id": self.product.id},
                {"name": "LOT-CHAR-B", "product_id": self.product.id},
            ]
        )
        production.lot_producing_ids = first_lot
        worksheet = self.create_worksheet(
            "coding_20260810", self.create_check("coding_20260810", production)
        )

        production.lot_producing_ids = second_lot

        self.assertEqual(worksheet.x_coding_log_id.lot_id, second_lot)
        self.assertEqual(worksheet.x_lot_id, second_lot)
