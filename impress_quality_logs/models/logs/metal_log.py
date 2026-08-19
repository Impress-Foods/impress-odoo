import logging
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class MetalLog(models.Model):
    _inherit = "log.mixin"
    _name = "metal.log"
    _description = "Metal Detector Log"

    log_line_ids = fields.One2many(
        comodel_name="metal.log.line", inverse_name="metal_log_id"
    )
    monthly_signature = fields.Binary()
    monthly_signature_date = fields.Datetime(
        compute="_compute_monthly_signature_date",
        inverse="_inverse_monthly_signature_date",
        store=True,
    )

    @api.depends("monthly_signature")
    def _compute_monthly_signature_date(self):
        for rec in self:
            if rec.monthly_signature:
                rec.monthly_signature_date = datetime.now(tz=timezone.utc)

    def _inverse_monthly_signature_date(self):
        return

    def action_view_metal_lines(self):
        self.ensure_one()
        action = {
            "res_model": "metal.log.line",
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "domain": Domain("metal_log_id", "=", self.id),
        }
        return action
