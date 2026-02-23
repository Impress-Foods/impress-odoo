from odoo import fields, models


class MrpCampaignAddDemand(models.TransientModel):
    _name = "mrp.campaign.add.demand"
    _description = "Wizard to Add Demand to an existing MRP Campaign"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Campaign",
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get("active_id"),
    )

    demand_move_ids = fields.Many2many(
        "stock.move",
        string="Demands to Add",
        help="Select the demand moves you want to add to this campaign.",
    )

    def add_demands(self):
        """
        Adds the selected demand moves to the parent campaign.
        It finds or creates campaign lines and appends the moves.
        """
        self.ensure_one()
        campaign = self.campaign_id
        moves_to_add = self.demand_move_ids

        if not moves_to_add:
            return {"type": "ir.actions.act_window_close"}

        products = moves_to_add.mapped("product_id")
        boms_by_product = self.env["mrp.bom"]._bom_find(products=products)

        grouped_moves = moves_to_add.grouped("product_id")

        for product, _moves in grouped_moves.items():
            bom = boms_by_product.get(product)
            # Find an existing line for this product/bom combination
            demand_line = campaign.demand_line_ids.filtered(
                lambda line, product=product, bom=bom: (
                    line.product_id == product and line.bom_id == bom
                )
            )

            if not demand_line:
                demand_line = self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": campaign.id,
                        "product_id": product.id,
                        "bom_id": bom.id if bom else False,
                    }
                )

        return {"type": "ir.actions.act_window_close"}
