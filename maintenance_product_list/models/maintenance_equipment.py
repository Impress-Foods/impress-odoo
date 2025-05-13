import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Products",
    )

    product_count = fields.Integer(compute="_compute_product_count")

    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.product_ids)

    def action_view_maintenance_parts(self):
        self.ensure_one()
        action = {
            "name": _("Maintenance Parts"),
            "type": "ir.actions.act_window",
            "view_mode": "tree,form",
            "res_model": "product.product",
            "domain": [("maintenance_equipment_ids", "=", self.id)],
        }
        return action
