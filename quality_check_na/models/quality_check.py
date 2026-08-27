from odoo import api, fields, models
from odoo.exceptions import UserError


class QualityCheck(models.Model):
    _inherit = "quality.check"

    quality_state = fields.Selection(
        selection_add=[
            ("na", "Not Applicable"),
        ],
    )

    can_be_na = fields.Boolean()

    def do_na(self):
        self.ensure_one()
        if self.can_be_na:
            self.write(
                {
                    "quality_state": "na",
                    "user_id": self.env.user.id,
                    "control_date": fields.Datetime.now(),
                }
            )
        else:
            raise UserError(self.env._("This Quality Check cannot be set to N/A"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["can_be_na"] = (
                self.env["quality.point"].browse(vals["point_id"]).allow_na
            )
        return super().create(vals_list)

    @api.depends("quality_state")
    def _compute_measure_success(self):
        res = super()._compute_measure_success()
        for rec in self:
            if rec.quality_state == "na":
                rec.measure_success = "pass"
        return res

    def action_na_and_next(self):
        self.ensure_one()
        self.do_na()
        result = self._next()
        return result if isinstance(result, dict) else {"next_check_id": result}
