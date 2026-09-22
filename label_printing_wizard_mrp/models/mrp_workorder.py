from odoo import models


class MrpWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    def action_open_label_wizard(self) -> dict:
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "res_model": "label.wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_product_id": self.product_id.id,
                "default_product_uom_qty": self.production_id.product_uom_qty,
            },
        }

        return action
