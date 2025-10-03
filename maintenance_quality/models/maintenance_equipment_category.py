from odoo import models


class MaintenanceEquipmentCategory(models.Model):
    _name = "maintenance.equipment.category"
    _inherit = ["maintenance.equipment.category", "maintenance.quality.mixin"]
