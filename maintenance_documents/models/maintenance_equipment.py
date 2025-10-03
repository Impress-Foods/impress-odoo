import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    document_count = fields.Integer(compute="_compute_document_count")

    def _compute_document_count(self):
        Document = self.env["documents.document"]
        equipment_document_read_group = Document._read_group(
            [("res_model", "=", "maintenance.equipment"), ("res_id", "in", self.ids)],
            ["res_id"],
            ["__count"],
        )
        document_count_per_equipment_id = dict(equipment_document_read_group)
        for record in self:
            record.document_count = document_count_per_equipment_id.get(record.id, 0)

    def action_see_documents(self):
        self.ensure_one()
        return {
            "name": self.env._("Documents"),
            "domain": [("equipment_id", "=", self.id)],
            "res_model": "documents.document",
            "type": "ir.actions.act_window",
            "views": [(False, "kanban")],
            "view_mode": "kanban",
            "context": {
                "default_equipment_id": self.id,
                "default_res_model": "maintenance.equipment",
                "default_res_id": self.id,
                "searchpanel_default_folder_id": self.env.ref(
                    "maintenance_documents.documents_maintenance_folder"
                ).id,
            },
        }
