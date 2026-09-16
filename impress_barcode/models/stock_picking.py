from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_fields_stock_barcode(self) -> list[str]:
        return super()._get_fields_stock_barcode() + ["origin"]

    def action_open_picking_backend_form(self) -> dict:
        self.ensure_one()
        view = self.env.ref("stock.view_picking_form")
        return {
            "name": self.env._("Open picking"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "views": [(view.id, "form")],
            "res_id": self.id,
        }
