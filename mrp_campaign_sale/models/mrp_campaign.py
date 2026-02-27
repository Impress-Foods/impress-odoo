from odoo import api, fields, models


class MrpCampaign(models.Model):
    _inherit = "mrp.campaign"

    sale_order_ids = fields.Many2many(
        "sale.order", compute="_compute_sale_order_ids", store=True
    )
    sale_order_count = fields.Integer(compute="_compute_sale_order_count")

    @api.depends("sale_order_ids")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = len(rec.sale_order_ids)

    @api.depends("demand_line_ids", "demand_line_ids.sale_order_ids")
    def _compute_sale_order_ids(self):
        for rec in self:
            rec.sale_order_ids = rec.demand_line_ids.mapped("sale_order_ids")

    def action_view_sos(self):
        self.ensure_one()
        if self.sale_order_count == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "views": [[False, "form"]],
                "res_id": self.sale_order_ids[0].id,
                "target": "current",
            }
        else:
            return {
                "type": "ir.actions.act_window",
                "name": "Sale orders for %s" % self.name,
                "res_model": "sale.order",
                "domain": [("id", "in", self.sale_order_ids.ids)],
                "view_mode": "tree,form",
                "target": "current",
            }
