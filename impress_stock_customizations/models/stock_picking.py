from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    minimum_shelf_life = fields.Integer(related="partner_id.minimum_shelf_life")

    def action_print_online_label(self):
        self.ensure_one()
        return self.env.ref(
            "impress_stock_customizations.action_report_online_sale_label"
        ).report_action(self, config=False)
