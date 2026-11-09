"""Shared fixtures for the impress_quality_worksheets characterization tests.

These tests describe how the worksheet <-> log <-> log line <-> quality check
linking behaves *today*. They are a safety net for future changes: a failing
test means behaviour changed, which must be a deliberate decision.
"""

from typing import Any

from odoo import Command
from odoo.models import BaseModel
from odoo.tests import common

from odoo.addons.mrp.models.mrp_production import MrpProduction
from odoo.addons.quality.models.quality import QualityCheck, QualityPoint
from odoo.addons.worksheet.models.worksheet_template import WorksheetTemplate

MODULE = "impress_quality_worksheets"

# Released worksheet templates, keyed by a short name used in subTests.
# value: (template xmlid, worksheet field -> log, worksheet field -> lines, log model)
TEMPLATES: dict[str, tuple[str, str, str | None, str]] = {
    "hpp_20250203": (
        "ws_hpp_20250203",
        "x_hpp_log_id",
        "x_hpp_log_line_ids",
        "hpp.log",
    ),
    "metal_20250203": (
        "ws_metal_20250203",
        "x_metal_log_id",
        "x_metal_log_line_ids",
        "metal.log",
    ),
    "metal_large_20260303": (
        "ws_metal_large_20260303",
        "x_metal_log_id",
        "x_metal_log_line_ids",
        "metal.log",
    ),
    "weight_20260305": (
        "ws_weight_20260305",
        "x_weight_log_id",
        "x_weight_log_line_ids",
        "weight.log",
    ),
    "x_ray_20250303": (
        "ws_x_ray_20250303",
        "x_x_ray_log_id",
        "x_x_ray_log_line_ids",
        "x_ray.log",
    ),
    "x_ray_large_20251126": (
        "ws_x_ray_large_20251126",
        "x_x_ray_log_id",
        "x_x_ray_log_line_ids",
        "x_ray.log",
    ),
    "coding_20250303": ("ws_coding_20250303", "x_coding_log_id", None, "coding.log"),
    "coding_20260810": ("ws_coding_20260810", "x_coding_log_id", None, "coding.log"),
}

# Name of the Many2one from each log line model to its log.
LINE_LOG_FIELD: dict[str, str] = {
    "hpp.log": "hpp_log_id",
    "metal.log": "metal_log_id",
    "weight.log": "weight_log_id",
    "x_ray.log": "x_ray_log_id",
}


class WorksheetCase(common.TransactionCase):
    """Base class: one lot-tracked product, one MO, one quality point per template."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.worksheet_test_type = cls.env.ref(
            "quality_control_worksheet.test_type_worksheet"
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Characterization Product",
                "is_storable": True,
                "tracking": "lot",
                "qty_multiple": 6,
                "use_expiration_date": True,
                "expiration_time": 30,
            }
        )
        cls.production: MrpProduction = cls._create_production()
        cls.points: dict[str, QualityPoint] = {
            key: cls.env["quality.point"].create(
                {
                    "name": f"QCP {key}",
                    "test_type_id": cls.worksheet_test_type.id,
                    "worksheet_template_id": cls.template(key).id,
                }
            )
            for key in TEMPLATES
        }

    # -- helpers ------------------------------------------------------------

    @classmethod
    def template(cls, key: str) -> WorksheetTemplate:
        return cls.env.ref(f"{MODULE}.{TEMPLATES[key][0]}")

    @classmethod
    def _create_production(cls) -> MrpProduction:
        return cls.env["mrp.production"].create(
            {"product_id": cls.product.id, "product_qty": 12}
        )

    def create_check(
        self, key: str, production: MrpProduction | None = None
    ) -> QualityCheck:
        production = production if production is not None else self.production
        return self.env["quality.check"].create(
            {
                "point_id": self.points[key].id,
                "production_id": production.id,
                "product_id": production.product_id.id,
            }
        )

    def wizard_env_for(self, check: QualityCheck) -> dict[str, Any]:
        """Context the standard wizard flow passes to the worksheet form.

        Mirrors quality_control_worksheet's action_open_quality_check_wizard:
        the wizard exists before the worksheet is saved, and the worksheet
        form receives both quality_wizard_id and default_x_quality_check_id.
        """
        wizard = self.env["quality.check.wizard"].create(
            {"check_ids": [Command.set(check.ids)], "current_check_id": check.id}
        )
        return {
            "quality_wizard_id": wizard.id,
            "default_x_quality_check_id": check.id,
        }

    def create_worksheet(
        self,
        key: str,
        check: QualityCheck,
        line_vals: list[dict[str, Any]] | None = None,
        use_wizard: bool = True,
        **extra_vals: Any,
    ) -> BaseModel:
        """Save a worksheet the way the form does: lines nested in one create."""
        template = self.template(key)
        _xmlid, _log_field, lines_field, _log_model = TEMPLATES[key]
        vals: dict[str, Any] = {"x_quality_check_id": check.id, **extra_vals}
        if line_vals:
            assert lines_field, f"{key} has no log lines"
            vals[lines_field] = [Command.create(v) for v in line_vals]
        ctx = self.wizard_env_for(check) if use_wizard else {}
        model = self.env[template.model_id.model].with_context(**ctx)
        worksheet = model.create(vals)
        # Each form save is its own request, which ends with a flush. Without
        # it, stored computes of several worksheets run in one batch, which
        # never happens from the UI.
        self.env.flush_all()
        return worksheet

    @staticmethod
    def line_vals(key: str, index: int = 1) -> dict[str, Any]:
        """Minimal valid values for one line of the given template's log type."""
        log_model = TEMPLATES[key][3]
        if log_model == "hpp.log":
            return {
                "cycle_number": index,
                "cycle_time": "120sec",
                "barrel_1_qty": 10,
                "barrel_2_qty": 10,
                "barrel_3_qty": 10,
                "barrel_4_qty": 10,
            }
        return {"notes": f"line {index}"}
