import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    maintenance_open_count_preventive = fields.Integer(
        string="Current Preventive", compute="_compute_maintenance_count_preventive"
    )
    maintenance_open_count_corrective = fields.Integer(
        string="Current Corrective", compute="_compute_maintenance_count_corrective"
    )

    technician_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        domain=(
            "[('groups_id', 'in',[ref('hr_maintenance.group_maintenance_manager')])]"
        ),
    )

    @api.depends("maintenance_count")
    def _compute_maintenance_count_preventive(self):
        for record in self:
            record.maintenance_open_count_preventive = len(
                record.maintenance_ids.filtered(
                    lambda mr: not mr.stage_id.done
                    and not mr.archive
                    and mr.maintenance_type == "preventive"
                )
            )

    @api.depends("maintenance_count")
    def _compute_maintenance_count_corrective(self):
        for record in self:
            record.maintenance_open_count_corrective = len(
                record.maintenance_ids.filtered(
                    lambda mr: not mr.stage_id.done
                    and not mr.archive
                    and mr.maintenance_type == "corrective"
                )
            )

    def action_get_requests(self):
        self.ensure_one()
        return {
            "res_model": "maintenance.request",
            "type": "ir.actions.act_window",
            "view_mode": "kanban,form",
            "name": "Maintenance Requests",
            "domain": [("id", "in", self.maintenance_ids.ids)],
        }
