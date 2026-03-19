from odoo import api, fields, models


class MrpCampaignCreatorDirect(models.TransientModel):
    _name = "mrp.campaign.creator.direct"
    _description = "Wizard to create MRP Campaigns from stock moves"
    _inherit = "mrp.campaign.creator"

    # ----------------------------------------------------------------------
    # FIELDS
    # ----------------------------------------------------------------------
    demand_move_ids = fields.Many2many("stock.move")
    available_demand_move_ids = fields.Many2many(
        comodel_name="stock.move",
        compute="_compute_available_demand_move_ids",
        store=False,
    )

    # ----------------------------------------------------------------------
    # COMPUTES
    # ----------------------------------------------------------------------
    @api.depends("product_id")
    def _compute_available_demand_move_ids(self):
        for rec in self:
            if not rec.product_id:
                rec.available_demand_move_ids = []
                continue

            anchor_product = rec.product_id
            available_moves = self.env["stock.move"].search(
                [
                    ("product_id.anchor_product_id", "=", anchor_product.id),
                    ("campaign_can_be_added", "=", True),
                ]
            )
            rec.available_demand_move_ids = available_moves

    # ----------------------------------------------------------------------
    # ONCHANGES
    # ----------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.demand_move_ids = [(5, 0, 0)]

    # ----------------------------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------------------------
    def make_campaign(self):
        self.ensure_one()
        if not self.product_id:
            return {}

        campaign = self.env["mrp.campaign"].create(
            {
                "product_id": self.product_id.id,
                "date_planned_start": self.planned_date,
                "workflow_type": "direct",
            }
        )
        self._create_demands(campaign)

        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "views": [[False, "form"]],
            "res_id": campaign.id,
            "target": "current",
        }

    # ----------------------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------------------
    def _create_demands(self, campaign):
        self.ensure_one()
        if not self.demand_move_ids:
            return

        products = self.demand_move_ids.mapped("product_id")
        boms_by_product = self.env["mrp.bom"]._bom_find(products=products)

        grouped_moves = self.demand_move_ids.grouped("product_id")
        for product, moves in grouped_moves.items():
            bom = boms_by_product.get(product)
            demand = self.env["mrp.campaign.demand"].create(
                {
                    "campaign_id": campaign.id,
                    "product_id": product.id,
                    "bom_id": bom.id if bom else False,
                    "target_qty": sum(m.product_uom_qty for m in moves),
                }
            )
            proxy_vals = [
                {
                    "demand_id": demand.id,
                    "move_id": m.id,
                    "promised_qty": m.product_uom_qty,
                }
                for m in moves
            ]
            self.env["mrp.campaign.demand.proxy"].create(proxy_vals)
