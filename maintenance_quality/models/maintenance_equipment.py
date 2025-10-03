import logging

from odoo import api, fields, models

from odoo.addons.quality.models.quality import QualityPoint

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    quality_point_ids = fields.Many2many("quality.point", string="Quality Points")

    quality_point_count = fields.Integer(
        "Quality Points Count", compute="_compute_quality_point_count"
    )

    def _get_all_relevent_qcps(self) -> QualityPoint:
        self.ensure_one()
        qcp = self.env["quality.point"]
        return qcp.search(
            [
                "|",
                "|",
                "&",
                ("equipment_ids", "!=", False),
                ("equipment_ids", "in", [self.id]),
                "&",
                ("equipment_category_ids", "!=", False),
                ("equipment_category_ids", "in", [self.category_id.id]),
                "&",
                ("workcenter_ids", "!=", False),
                ("workcenter_ids", "in", [self.workcenter_id.id]),
            ]
        )

    @api.depends("quality_point_ids")
    def _compute_quality_point_count(self):
        for rec in self:
            if rec.id:
                rec.quality_point_count = len(rec._get_all_relevent_qcps())
            else:
                rec.quality_point_count = 0

    def action_view_quality_points(self):
        self.ensure_one()
        qcps = self._get_all_relevent_qcps()
        if len(qcps) == 1:
            action = {
                "name": self.env._("Quality Points"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "quality.point",
                "res_id": qcps[0].id,
            }
        else:
            action = {
                "name": self.env._("Quality Points"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "quality.point",
                "domain": [("id", "in", [qcp.id for qcp in qcps])],
            }

        return action
