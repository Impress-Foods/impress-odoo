from odoo import fields, models


class MrpCampaignLine(models.Model):
    _inherit = "mrp.campaign.line"

    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Billing SOL",
    )

    def _make_production_order(self) -> list[dict]:
        values = super()._make_production_order()
        if self.sale_order_line_id:
            for v in values:
                v["billing_sale_order_line_id"] = self.sale_order_line_id.id
        return values
