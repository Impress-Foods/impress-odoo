import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class weightLog(models.Model):
    _name = "weight.log"
    _inherit = "log.mixin"
    _description = "weight log"

    log_line_ids = fields.One2many(
        comodel_name="weight.log.line", inverse_name="weight_log_id"
    )

    nominal_weight = fields.Float()

    def action_view_weight_lines(self):
        self.ensure_one()
        action = {
            "res_model": "weight.log.line",
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "domain": [("weight_log_id", "=", self.id)],
        }
        return action
