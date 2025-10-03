import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    maintenance_request_id = fields.Many2one(
        "maintenance.request", "Maintenance Request"
    )

    equipment_id = fields.Many2one(
        "maintenance.equipment",
        "Equipment",
    )

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        "Workcenter",
    )

    def do_alert(self):
        self.ensure_one()
        res = super().do_alert()
        alert = self.env["quality.alert"].browse(res["res_id"])
        alert.write({"maintenance_request_id": self.maintenance_request_id})
        return res

    def action_view_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Maintenance Request"),
            "res_model": "maintenance.request",
            "views": [(False, "form")],
            "res_id": self.maintenance_request_id.id,
        }
