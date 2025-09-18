import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class LomaLog(models.Model):
    _name = "loma.log"
    _inherit = "log.mixin"
    _description = "LOMA log"

    log_line_ids = fields.One2many(
        comodel_name="loma.log.line", inverse_name="loma_log_id"
    )

    lower_limit = fields.Float()
    upper_limit = fields.Float()
    nominal_weight = fields.Float()

    def action_view_loma_lines(self):
        self.ensure_one()
        action = {
            "res_model": "loma.log.line",
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "domain": [("loma_log_id", "=", self.id)],
        }
        return action
