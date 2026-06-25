import logging
from random import randint

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MaintenanceTeamTag(models.Model):
    _name = "maintenance.team.tag"
    _description = "Maintenance Team Tag"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(
        string="Color Index", default=lambda self: self._get_default_color
    )
    _check_unique_tag_name = models.Constraint(
        "UNIQUE(name)", "Tag name must be unique!"
    )


class MaintenanceTeam(models.Model):
    _inherit = "maintenance.team"

    team_tag_ids = fields.Many2many("maintenance.team.tag", string="Team Tag")
