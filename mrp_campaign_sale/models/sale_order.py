from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    mrp_campaign_ids = fields.Many2many("mrp.campaign")
    mrp_campaign_count = fields.Integer(compute="_compute_mrp_campaign_count")

    @api.depends("mrp_campaign_ids")
    def _compute_mrp_campaign_count(self):
        for rec in self:
            rec.mrp_campaign_count = len(rec.mrp_campaign_ids)

    def action_view_mrp_campaigns(self):
        self.ensure_one()
        if self.mrp_campaign_count == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "mrp.campaign",
                "views": [[False, "form"]],
                "res_id": self.mrp_campaign_ids[0].id,
                "target": "current",
            }
        else:
            return {
                "type": "ir.actions.act_window",
                "name": "Campaigns for %s" % self.name,
                "res_model": "mrp.campaign",
                "domain": [("id", "in", self.mrp_campaign_ids.ids)],
                "view_mode": "tree,form",
                "target": "current",
            }
