from odoo import api, fields, models


class MrpCampaignDemand(models.Model):
    _name = "mrp.campaign.demand"
    _description = "Manufacturing Campaign Demand Line"

    campaign_id = fields.Many2one(
        "mrp.campaign", string="Campaign", required=True, ondelete="cascade"
    )
    campaign_line_id = fields.Many2one("mrp.campaign.line")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id"
    )
    qty = fields.Float(compute="_compute_qty")
    target_qty = fields.Float(
        string="Target Quantity",
        compute="_compute_target_qty",
        inverse="_inverse_target_qty",
        store=True,
    )

    move_dest_ids = fields.Many2many(
        "stock.move",
        string="Destination Moves",
        help="Moves that this production will fulfill.",
    )

    product_uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Bill of Materials",
        help="The specific BoM to be used for manufacturing the product on this line.",
    )

    def _get_anchor_factor(self) -> float:
        self.ensure_one()
        return self.campaign_line_id._get_anchor_factor()

    def _compute_qty(self):
        for rec in self:
            rec.qty = sum(rec.move_dest_ids.mapped("product_uom_qty"))

    @api.depends("qty")
    def _compute_target_qty(self):
        for rec in self:
            rec.target_qty = rec.qty

    def _inverse_target_qty(self):
        pass
