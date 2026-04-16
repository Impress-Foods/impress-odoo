import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MetalLogLine(models.Model):
    _name = "metal.log.line"
    _inherit = "log_line.mixin"
    _description = "Metal_log_line"
    _rec_name = "sequence"

    _check_sequence = models.Constraint(
        "UNIQUE(sequence)",
        "Sequence Number must be unique!",
    )

    metal_log_id = fields.Many2one(
        comodel_name="metal.log", compute="_compute_metal_log_id", store=True
    )

    sequence = fields.Char(default=lambda self: self.env._("New"), copy=False)

    calibration = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    ejection = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])

    reject_value = fields.Float()
    ferrous = fields.Integer("Ferrous (2.0 mm)")
    non_ferrous = fields.Integer("Non ferrous (2.5 mm)")
    stainless = fields.Integer("Stainless (3.5 mm)")

    ferrous_large = fields.Integer("Ferrous (2.0 mm)")
    non_ferrous_large = fields.Integer("Non ferrous (3.0 mm)")
    stainless_large = fields.Integer("Stainless (4.0 mm)")

    torque = fields.Integer()
    mean_weight = fields.Float()

    global_success = fields.Boolean(compute="_compute_global_success")

    @api.depends(
        "calibration", "ejection", "reject_value", "ferrous", "non_ferrous", "stainless"
    )
    def _compute_global_success(self):
        for rec in self:
            ferrous_check = rec.ferrous > rec.reject_value
            non_ferrous_check = rec.non_ferrous > rec.reject_value
            stainless_check = rec.stainless > rec.reject_value
            standard_check = all([ferrous_check, non_ferrous_check, stainless_check])

            ferrous_check_large = rec.ferrous_large > rec.reject_value
            non_ferrous_check_large = rec.non_ferrous_large > rec.reject_value
            stainless_check_large = rec.stainless_large > rec.reject_value
            large_check = all(
                [ferrous_check_large, non_ferrous_check_large, stainless_check_large]
            )

            indicator_check = any([standard_check, large_check])
            calib_check = rec.calibration == "ok"
            ejection_check = rec.ejection == "ok"
            rec.global_success = all(
                [
                    indicator_check,
                    calib_check,
                    ejection_check,
                ]
            )

    @api.depends("quality_check_id")
    def _compute_metal_log_id(self):
        for record in self:
            # Get the current worksheet field
            ws = record.active_worksheet_field
            if ws:
                record.metal_log_id = record[ws].x_metal_log_id
            else:
                record.metal_log_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == self.env._("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "metal_log_line"
                ) or self.env._("New")
        return super().create(vals_list)

    def action_view_log(self):
        self.ensure_one()
        action = {
            "res_model": "metal.log",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.metal_log_id.id,
        }
        return action
