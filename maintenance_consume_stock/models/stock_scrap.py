from odoo import fields, models


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    maintenance_request_id = fields.Many2one(
        comodel_name="maintenance.request",
        string="Maintenance Request",
        ondelete="cascade",
    )

    product_vendor_code = fields.Char(related="product_id.vendor_code")

    def action_view_maintenance_request(self):
        self.ensure_one()

        action = {
            "name": self.env._("Maintenance Request"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "maintenance.request",
            "res_id": self.maintenance_request_id.id,
        }

        return action
