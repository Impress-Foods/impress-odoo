from odoo import api, fields, models


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

    valid_move_ids = fields.Many2many(
        "stock.move",
        "inverse_valid_move_ids",
    )

    demand_move_ids = fields.Many2many(
        "stock.move",
        string="Demands to Add",
        help="Select the demand moves you want to add to this campaign.",
    )

    @api.model
    def default_get(self, fields_list):  # pragma: no coverage
        res = super().default_get(fields_list)

        if "valid_move_ids" in fields_list:
            active_id = self.env.context.get("active_id", False)

            if active_id:
                campaign = self.env["mrp.campaign"].browse(active_id)

                res["valid_move_ids"] = self._get_valid_move_ids(campaign)
        return res

    @api.model
    def _get_valid_move_ids(self, campaign):
        anchor_product = campaign.product_id
        return self.env["stock.move"].search(
            [
                ("product_id.anchor_product_id", "=", anchor_product.id),
                ("campaign_can_be_added", "=", True),
            ]
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

        grouped_moves = moves_to_add.grouped("product_id")
        proxy_values = []
        for product, moves in grouped_moves.items():
            # Find an existing line for this product/bom combination
            demand_line = campaign.demand_line_ids.filtered(
                lambda line, product=product: line.product_id == product
            )

            if not demand_line:
                demand_line = self.env["mrp.campaign.demand"].create(
                    {
                        "campaign_id": campaign.id,
                        "product_id": product.id,
                    }
                )

            proxy_values += [
                {
                    "move_id": move.id,
                    "demand_id": demand_line.id,
                    "promised_qty": move.campaign_qty_to_supply,
                }
                for move in moves
            ]

        self.env["mrp.campaign.demand.proxy"].create(proxy_values)
        return {"type": "ir.actions.act_window_close"}
