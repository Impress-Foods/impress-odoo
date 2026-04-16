import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WeightLogLine(models.Model):
    _name = "weight.log.line"
    _inherit = "log_line.mixin"
    _description = "Weight Log Line"
    _rec_name = "sequence"

    _check_sequence = models.Constraint(
        "UNIQUE(sequence)", "Sequence Number must be unique!"
    )

    sequence = fields.Char(default=lambda self: self.env._("New"), copy=False)
    weight_log_id = fields.Many2one(
        comodel_name="weight.log", compute="_compute_weight_log_id", store=True
    )

    nominal_weight = fields.Float(
        related="weight_log_id.nominal_weight",
        store=True,
        depends=["weight_log_id.nominal_weight"],
    )

    measure_1 = fields.Float()
    measure_2 = fields.Float()
    measure_3 = fields.Float()
    measure_4 = fields.Float()
    measure_5 = fields.Float()

    is_seal_ok = fields.Boolean("Seal Ok")
    is_weight_ok = fields.Boolean("Weight Ok")

    @api.depends("quality_check_id")
    def _compute_weight_log_id(self):
        for record in self:
            # Get the current worksheet field
            ws = record.active_worksheet_field
            if ws:
                record.weight_log_id = record[ws].x_weight_log_id
            else:
                record.weight_log_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == self.env._("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "weight_log_line"
                ) or self.env._("New")
        return super().create(vals_list)

    def action_view_log(self):
        self.ensure_one()
        action = {
            "res_model": "weight.log",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.weight_log_id.id,
        }
        return action
