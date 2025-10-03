import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _name = "mrp.workcenter"
    _inherit = ["mrp.workcenter", "maintenance.quality.mixin"]
