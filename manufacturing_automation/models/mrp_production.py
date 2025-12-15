from odoo import api, fields, models


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Campaign",
        ondelete="restrict",
    )

    associated_campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Associated Campaign",
        compute="_compute_associated_campaign_id",
        store=False,  # Dynamic to ensure it's always accurate
    )

    campaign_product_qty = fields.Float(compute="_compute_associated_campaign_id")

    @api.depends("campaign_id", "move_raw_ids")
    def _compute_associated_campaign_id(self):
        for mo in self:
            if mo.campaign_id:
                mo.associated_campaign_id = mo.campaign_id

            else:
                campaign = self.env["mrp.campaign"].search(
                    [("demand_move_ids", "in", mo.move_raw_ids.ids)], limit=1
                )
                mo.associated_campaign_id = campaign

            if mo.associated_campaign_id:
                product = mo.associated_campaign_id.product_id
                move = mo.move_raw_ids.filtered_domain(
                    [("product_id", "=", product.id)]
                )
                mo.campaign_product_qty = move.product_uom_qty

    def action_view_campaign(self):
        self.ensure_one()
        if not self.associated_campaign_id:
            return
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "res_id": self.associated_campaign_id.id,
            "view_mode": "form",
            "target": "current",
        }
