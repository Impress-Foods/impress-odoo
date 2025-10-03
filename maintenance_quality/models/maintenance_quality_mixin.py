import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceQualityMixin(models.AbstractModel):
    _name = "maintenance.quality.mixin"
    _description = "Maintenance Quality Mixin"

    quality_point_ids = fields.Many2many("quality.point", string="Quality Points")

    quality_point_count = fields.Integer(
        "Quality Points Count", compute="_compute_quality_point_count"
    )

    @api.depends("quality_point_ids")
    def _compute_quality_point_count(self):
        for rec in self:
            rec.quality_point_count = len(rec.quality_point_ids)

    def action_view_quality_points(self):
        self.ensure_one()
        if len(self.quality_point_ids) == 1:
            return {
                "name": self.env._("Quality Points"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "quality.point",
                "res_id": self.quality_point_ids[0].id,
            }
        else:
            return {
                "name": self.env._("Quality Points"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "quality.point",
                "domain": [("id", "in", self.quality_point_ids.ids)],
            }
