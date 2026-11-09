import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Xray_log_line(models.Model):
    _name = "x_ray.log.line"
    _inherit = "log_line.mixin"
    _rec_name = "sequence"
    _description = "X-Ray Detector Log Line"

    _check_sequence = models.Constraint(
        "UNIQUE(sequence)", "Sequence Number must be unique!"
    )

    sequence = fields.Char(default=lambda self: self.env._("New"), copy=False)

    _log_field = "x_ray_log_id"
    x_ray_log_id = fields.Many2one(comodel_name="x_ray.log")

    reject_value = fields.Integer()

    stainless_detection_value = fields.Integer("Stainless detection value (1.0 mm)")
    ceramic_detection_value = fields.Integer("Ceramic detection value (2.381 mm)")
    glass_detection_value = fields.Integer("Glass detection value (2.381 mm)")

    stainless_detection_large_value = fields.Integer(
        "Stainless detection value (1.2 mm)"
    )
    ceramic_detection_large_value = fields.Integer("Ceramic detection value (3.0 mm)")
    glass_detection_large_value = fields.Integer("Glass detection value (3.0 mm)")

    ejection = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    last_check_for_product = fields.Boolean()

    total_qty = fields.Integer("Total Quantity")
    reject_qty = fields.Integer("Reject Quantity")
    average = fields.Integer()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == self.env._("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "x_ray_log_line"
                ) or self.env._("New")
        return super().create(vals_list)

    def action_view_log(self):
        self.ensure_one()
        action = {
            "res_model": "x_ray.log",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.x_ray_log_id.id,
        }
        return action
