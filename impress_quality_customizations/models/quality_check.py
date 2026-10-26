import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    signature = fields.Binary()
    is_ccp = fields.Boolean(related="point_id.is_ccp")

    def action_view_production(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Production Order",
            "res_model": "mrp.production",
            "views": [(False, "form")],
            "res_id": self.production_id.id,
        }

    def action_view_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Transfer",
            "res_model": "stock.picking",
            "views": [(False, "form")],
            "res_id": self.picking_id.id,
        }

    def do_alert(self) -> dict:
        """Keep the production and transfer the check was done on."""
        self.ensure_one()
        action = super().do_alert()
        alert = self.env["quality.alert"].browse(action["res_id"])
        values = {}
        if self.picking_id and not alert.picking_id:
            values["picking_id"] = self.picking_id.id
        if self.production_id and not alert.production_id:
            values["production_id"] = self.production_id.id
        if values:
            alert.write(values)
        return action
