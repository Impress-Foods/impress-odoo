"""Characterization: values computed on logs and lines, as filled from worksheets."""

import base64

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import WorksheetCase

# 1x1 transparent PNG, used as signature initials.
PIXEL = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000005000100e2216bc4"
        "0000000049454e44ae426082"
    )
)


@tagged("post_install", "-at_install")
class TestHppQuantities(WorksheetCase):
    def _hpp_worksheet(self, cycles: int = 2):
        production = self._create_production()
        return self.create_worksheet(
            "hpp_20250203",
            self.create_check("hpp_20250203", production),
            [self.line_vals("hpp_20250203", i) for i in range(1, cycles + 1)],
        )

    def test_quantities_and_cases(self):
        worksheet = self._hpp_worksheet(cycles=2)
        log = worksheet.x_hpp_log_id

        # The worksheet's related fields write through to the log.
        worksheet.write({"x_qty_redone": 2, "x_qty_scrapped": 1, "x_qty_quality": 1})

        self.assertEqual(log.qty_redone, 2)
        self.assertEqual(log.qty_total, 80)
        self.assertEqual(log.qty_produced, 76)
        self.assertEqual(log.qty_cases, 12)  # floor(76 / 6)
        self.assertEqual(log.production_id.hpp_qty_cases, 12)

    def test_cases_without_qty_per_case(self):
        self.product.qty_multiple = 0
        log = self._hpp_worksheet(cycles=1).x_hpp_log_id
        self.assertEqual(log.qty_cases, log.qty_produced)

    def test_cleaning_cycle_requires_empty_barrels(self):
        cleaning = {**self.line_vals("hpp_20250203", 1), "is_cleaning_cycle": True}
        with self.assertRaises(ValidationError):
            self.create_worksheet(
                "hpp_20250203", self.create_check("hpp_20250203"), [cleaning]
            )

    def test_empty_cleaning_cycle_counts_zero(self):
        cleaning = {
            "cycle_number": 1,
            "cycle_time": "120sec",
            "is_cleaning_cycle": True,
        }
        worksheet = self.create_worksheet(
            "hpp_20250203", self.create_check("hpp_20250203"), [cleaning]
        )
        self.assertEqual(worksheet.x_hpp_log_line_ids.total_qty, 0)

    def test_cycle_number_unique_per_production(self):
        worksheet = self._hpp_worksheet(cycles=1)
        check = worksheet.x_quality_check_id
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(IntegrityError),
            self.env.cr.savepoint(),
        ):
            self.create_worksheet(
                "hpp_20250203", check, [self.line_vals("hpp_20250203", 1)]
            )
            self.env.flush_all()


@tagged("post_install", "-at_install")
class TestMetalSuccess(WorksheetCase):
    def _line(self, **vals):
        worksheet = self.create_worksheet(
            "metal_20250203",
            self.create_check("metal_20250203", self._create_production()),
            [{"calibration": "ok", "ejection": "ok", "reject_value": 50, **vals}],
        )
        return worksheet.x_metal_log_line_ids

    def test_standard_indicators_above_reject_value_pass(self):
        line = self._line(ferrous=60, non_ferrous=60, stainless=60)
        self.assertTrue(line.global_success)

    def test_one_standard_indicator_at_reject_value_fails(self):
        line = self._line(ferrous=60, non_ferrous=50, stainless=60)
        self.assertFalse(line.global_success)

    def test_large_indicators_alone_pass(self):
        line = self._line(ferrous_large=60, non_ferrous_large=60, stainless_large=60)
        self.assertTrue(line.global_success)

    def test_failed_ejection_fails(self):
        line = self._line(ejection="not_ok", ferrous=60, non_ferrous=60, stainless=60)
        self.assertFalse(line.global_success)


@tagged("post_install", "-at_install")
class TestCodingLog(WorksheetCase):
    def test_2025_fields_write_through_and_drive_global_success(self):
        checks = {
            "x_unit_check": "ok",
            "x_sleeve_check": "ok",
            "x_case_check": "ok",
            "x_subunit_check": "ok",
            "x_shelf_life_check": "ok",
            "x_keep_cold_check": "ok",
        }
        worksheet = self.create_worksheet(
            "coding_20250303", self.create_check("coding_20250303"), **checks
        )
        log = worksheet.x_coding_log_id
        self.assertEqual(log.unit_check, "ok")
        self.assertEqual(log.global_success_check, "ok")

    def test_2026_fields_do_not_drive_global_success(self):
        """global_success_check only reads the 2025 (deprecated) fields.

        A fully passing 2026 worksheet therefore computes 'not_ok'.
        """
        worksheet = self.create_worksheet(
            "coding_20260810",
            self.create_check("coding_20260810"),
            x_date_check="ok",
            x_packaging_check="ok",
        )
        log = worksheet.x_coding_log_id
        self.assertEqual(log.date_check, "ok")
        self.assertEqual(log.packaging_check, "ok")
        self.assertEqual(log.global_success_check, "not_ok")

    def test_2026_barcode_field_writes_to_packaging_check(self):
        """x_barcode_check is related to packaging_check, not barcode_check.

        It is not on the 2026-08-10 form, so operators cannot reach it.
        """
        worksheet = self.create_worksheet(
            "coding_20260810", self.create_check("coding_20260810")
        )
        worksheet.x_barcode_check = "not_ok"
        log = worksheet.x_coding_log_id
        self.assertEqual(log.packaging_check, "not_ok")
        self.assertFalse(log.barcode_check)

    def test_2026_barcode_na_is_rejected(self):
        """The worksheet field offers N/A, which packaging_check does not accept."""
        worksheet = self.create_worksheet(
            "coding_20260810", self.create_check("coding_20260810")
        )
        with self.assertRaises(ValueError):
            worksheet.x_barcode_check = "na"

    def test_shelf_life_follows_product_live(self):
        """Known exposure: past coding logs show the product's current shelf life."""
        worksheet = self.create_worksheet(
            "coding_20260810", self.create_check("coding_20260810")
        )
        self.assertEqual(worksheet.x_shelf_life, 30)

        self.product.expiration_time = 45

        self.assertEqual(worksheet.x_coding_log_id.shelf_life, 45)
        self.assertEqual(worksheet.x_shelf_life, 45)


@tagged("post_install", "-at_install")
class TestWeightLog(WorksheetCase):
    def test_nominal_weight_set_on_worksheet_reaches_lines(self):
        worksheet = self.create_worksheet(
            "weight_20260305",
            self.create_check("weight_20260305"),
            [self.line_vals("weight_20260305")],
            x_nominal_weight=250.0,
        )
        self.assertEqual(worksheet.x_weight_log_id.nominal_weight, 250.0)
        self.assertEqual(worksheet.x_weight_log_line_ids.nominal_weight, 250.0)


@tagged("post_install", "-at_install")
class TestSigningAndLocking(WorksheetCase):
    def setUp(self):
        super().setUp()
        self.env.user.sign_initials = PIXEL

    def test_sign_log_sets_signature_and_date(self):
        log = self.create_worksheet(
            "metal_20250203", self.create_check("metal_20250203")
        ).x_metal_log_id

        log.action_sign_log()

        self.assertEqual(log.signature, PIXEL)
        self.assertTrue(log.weekly_signature_date)

    def test_sign_log_keeps_existing_signature(self):
        log = self.create_worksheet(
            "metal_20250203", self.create_check("metal_20250203")
        ).x_metal_log_id
        log.signature = base64.b64encode(b"other")

        log.action_sign_log()

        self.assertEqual(log.signature, base64.b64encode(b"other"))

    def test_sign_log_line(self):
        line = self.create_worksheet(
            "metal_20250203",
            self.create_check("metal_20250203"),
            [self.line_vals("metal_20250203")],
        ).x_metal_log_line_ids

        line.sign_log_line()

        self.assertEqual(line.signature, PIXEL)

    def test_locked_line_can_still_be_written(self):
        """Known gap: is_locked is a flag only; write() does not enforce it."""
        line = self.create_worksheet(
            "metal_20250203",
            self.create_check("metal_20250203"),
            [self.line_vals("metal_20250203")],
        ).x_metal_log_line_ids
        line.action_lock()

        line.notes = "edited after lock"

        self.assertTrue(line.is_locked)
        self.assertEqual(line.notes, "edited after lock")
