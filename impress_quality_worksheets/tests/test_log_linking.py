"""How worksheets, logs, log lines and quality checks link together."""

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

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
class TestLogOwnsProduction(WorksheetCase):
    """The log is the anchor: one per type per production, found by production."""

    def test_split_mo_keeps_its_log(self):
        """Splitting an MO renames it to <name>-001; its log must still be found.

        Before 19.0.1.1.0 the lookup matched on name, so the next worksheet
        created a second log (seen in production on 138 logs).
        """
        for key, (_xmlid, log_field, _lines, log_model) in TEMPLATES.items():
            with self.subTest(template=key):
                production = self._create_production()
                first = self.create_worksheet(key, self.create_check(key, production))
                production.name = f"{production.name}-001"

                second = self.create_worksheet(key, self.create_check(key, production))

                self.assertEqual(second[log_field], first[log_field])
                self.assertEqual(
                    self.env[log_model].search_count(
                        [("production_id", "=", production.id)]
                    ),
                    1,
                )

    def test_get_or_create_sets_production_explicitly(self):
        production = self._create_production()
        check = self.create_check("metal_20250203", production)

        log = self.env["metal.log"]._get_or_create_for_production(production, check)

        self.assertEqual(log.production_id, production)
        self.assertEqual(log.quality_check_id, check)
        self.assertEqual(log.name, production.name)
        self.assertEqual(
            self.env["metal.log"]._get_or_create_for_production(production, check),
            log,
        )

    def test_log_created_with_check_only_gets_production(self):
        """Legacy creation path: production is filled from the check."""
        production = self._create_production()
        check = self.create_check("weight_20260305", production)

        log = self.env["weight.log"].create(
            {"name": production.name, "quality_check_id": check.id}
        )

        self.assertEqual(log.production_id, production)

    def test_one_log_per_type_per_production(self):
        production = self._create_production()
        self.env["x_ray.log"].create({"production_id": production.id})
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(IntegrityError),
            self.env.cr.savepoint(),
        ):
            self.env["x_ray.log"].create({"production_id": production.id})
            self.env.flush_all()

    def test_same_production_different_log_types_allowed(self):
        production = self._create_production()
        metal = self.env["metal.log"].create({"production_id": production.id})
        coding = self.env["coding.log"].create({"production_id": production.id})
        self.env.flush_all()
        self.assertEqual(metal.production_id, coding.production_id)


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

    def test_lines_without_wizard_context_get_check_from_worksheet(self):
        """Outside the wizard flow, the check comes from the worksheet.

        Before 19.0.1.1.0 these lines had no check and no production (13
        weight lines in production, created from the shop floor).
        """
        for key in LINE_TEMPLATES:
            _xmlid, log_field, lines_field, log_model = TEMPLATES[key]
            with self.subTest(template=key):
                production = self._create_production()
                check = self.create_check(key, production)
                worksheet = self.create_worksheet(
                    key, check, [self.line_vals(key)], use_wizard=False
                )

                line = worksheet[lines_field]
                self.assertEqual(line.quality_check_id, check)
                self.assertEqual(line.production_id, production)
                self.assertEqual(line[LINE_LOG_FIELD[log_model]], worksheet[log_field])

    def test_line_created_from_log_line_list_is_linked(self):
        """Lines created from the log's "view lines" list belong to the log.

        Uses the context returned by each log's action_view_<type>_lines, i.e.
        what the list's "New" button receives. Before 19.0.1.1.0 those lines
        were orphaned (13 in production). They take their check and their
        production from the log.
        """
        actions = {
            "hpp_20250203": "action_view_hpp_lines",
            "metal_20250203": "action_view_metal_lines",
            "weight_20260305": "action_view_weight_lines",
            "x_ray_20250303": "action_view_x_ray_lines",
        }
        for key, method in actions.items():
            _xmlid, log_field, _lines, log_model = TEMPLATES[key]
            with self.subTest(template=key):
                production = self._create_production()
                worksheet = self.create_worksheet(
                    key, self.create_check(key, production)
                )
                log = worksheet[log_field]
                action = getattr(log, method)()

                line = (
                    self.env[action["res_model"]]
                    .with_context(**action["context"])
                    .create(self.line_vals(key, 7))
                )

                self.assertEqual(line[LINE_LOG_FIELD[log_model]], log)
                self.assertIn(line, log.log_line_ids)
                self.assertIn(line, line.search(action["domain"]))
                self.assertEqual(line.quality_check_id, log.quality_check_id)
                self.assertTrue(line.quality_check_id)
                self.assertEqual(line.production_id, production)

    def test_explicit_log_wins_over_worksheet_log(self):
        production = self._create_production()
        other_log = self.env["metal.log"].create(
            {"production_id": self._create_production().id}
        )
        worksheet = self.create_worksheet(
            "metal_20250203",
            self.create_check("metal_20250203", production),
            [{**self.line_vals("metal_20250203"), "metal_log_id": other_log.id}],
        )

        line = worksheet.x_metal_log_line_ids
        self.assertEqual(line.metal_log_id, other_log)
        self.assertEqual(line.production_id, other_log.production_id)

    def test_line_on_log_takes_the_log_check(self):
        """Outside a worksheet and the wizard, the check comes from the log."""
        production = self._create_production()
        check = self.create_check("metal_20250203", production)
        log = self.env["metal.log"]._get_or_create_for_production(production, check)

        line = self.env["metal.log.line"].create({"metal_log_id": log.id})

        self.assertEqual(line.quality_check_id, check)

    def test_line_on_log_without_check_has_no_check(self):
        log = self.env["metal.log"].create(
            {"production_id": self._create_production().id}
        )
        line = (
            self.env["metal.log.line"]
            .with_context(**log.action_view_metal_lines()["context"])
            .create({"notes": "no check on log"})
        )
        self.assertEqual(line.metal_log_id, log)
        self.assertFalse(line.quality_check_id)

    def test_worksheet_check_wins_over_log_check(self):
        """A second check on the same production keeps its own lines' check."""
        production = self._create_production()
        first_check = self.create_check("metal_20250203", production)
        second_check = self.create_check("metal_20250203", production)
        self.create_worksheet("metal_20250203", first_check)

        worksheet = self.create_worksheet(
            "metal_20250203",
            second_check,
            [self.line_vals("metal_20250203")],
            use_wizard=False,
        )

        self.assertEqual(worksheet.x_metal_log_id.quality_check_id, first_check)
        self.assertEqual(worksheet.x_metal_log_line_ids.quality_check_id, second_check)


@tagged("post_install", "-at_install")
class TestLineProductionFromLog(WorksheetCase):
    """The line's production comes from its log, or its check when it has none."""

    def test_line_follows_its_log_production(self):
        worksheet = self.create_worksheet(
            "weight_20260305",
            self.create_check("weight_20260305"),
            [self.line_vals("weight_20260305")],
        )
        line = worksheet.x_weight_log_line_ids
        new_production = self._create_production()

        line.weight_log_id.production_id = new_production

        self.assertEqual(line.production_id, new_production)
        self.assertEqual(line.product_id, new_production.product_id)

    def test_line_moved_to_another_log_takes_its_production(self):
        worksheet = self.create_worksheet(
            "x_ray_20250303",
            self.create_check("x_ray_20250303"),
            [self.line_vals("x_ray_20250303")],
        )
        line = worksheet.x_x_ray_log_line_ids
        other_production = self._create_production()
        other_log = self.env["x_ray.log"].create({"production_id": other_production.id})

        line.x_ray_log_id = other_log

        self.assertEqual(line.production_id, other_production)

    def test_line_without_log_keeps_its_check_production(self):
        """Fallback that keeps existing log-less lines (19 in production) intact."""
        production = self._create_production()
        check = self.create_check("metal_20250203", production)

        line = self.env["metal.log.line"].create({"quality_check_id": check.id})

        self.assertFalse(line.metal_log_id)
        self.assertEqual(line.production_id, production)

    def test_line_without_log_or_check_has_no_production(self):
        line = self.env["metal.log.line"].create({"notes": "orphan"})
        self.assertFalse(line.production_id)
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
