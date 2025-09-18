import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Xray_log(models.Model):
    _name = "x_ray.log"
    _inherit = "log.mixin"
    _description = "X-Ray Detector Log"

    log_line_ids = fields.One2many(
        comodel_name="x_ray.log.line", inverse_name="x_ray_log_id"
    )

    average_threshold = fields.Integer()

    monthly_signature = fields.Binary()
    monthly_signature_date = fields.Datetime(
        compute="_compute_monthly_signature_date", store=True
    )

    @api.depends("monthly_signature")
    def _compute_monthly_signature_date(self):
        for rec in self:
            if rec.monthly_signature:
                rec.monthly_signature_date = datetime.now()

    def action_view_x_ray_lines(self):
        self.ensure_one()
        action = {
            "res_model": "x_ray.log.line",
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "domain": [("x_ray_log_id", "=", self.id)],
        }
        return action
