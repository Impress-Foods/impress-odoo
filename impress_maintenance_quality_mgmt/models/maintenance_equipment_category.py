import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MaintenanceEquipmentCategory(models.Model):
    _inherit = "maintenance.equipment.category"

    default_team_id = fields.Many2one("maintenance.team", string="Default Team")
