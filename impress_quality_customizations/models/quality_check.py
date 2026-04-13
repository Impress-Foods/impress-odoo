import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    signature = fields.Binary()

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
