from odoo import api, fields, models

from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.stock.models.stock_move import StockMove

from ..models.mrp_campaign import MrpCampaign


class MrpCampaignCreator(models.TransientModel):
    _name = "mrp.campaign.creator"
    _description = "Wizard to help the creation of MRP Campaigns"

    product_id = fields.Many2one(
        comodel_name="product.product",
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
        string="Anchor Product",
    )
    planned_date = fields.Date()

    demand_move_ids = fields.Many2many("stock.move")
    available_demand_move_ids = fields.Many2many(
        comodel_name="stock.move",
        compute="_compute_available_demand_move_ids",
        store=False,
    )

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

    @api.onchange("product_id")
    def _onchange_product_id(self):
        # Clear existing selection when product changes,
        #  as filter might make it invalid.
        if self.product_id:
            self.demand_move_ids = False

    def make_campaign(self):
        self.ensure_one()
        values = {
            "date_planned_start": self.planned_date,
            "product_id": self.product_id.id,
        }
        campaign_id: MrpCampaign = self.env["mrp.campaign"].create(values)

        products = self.demand_move_ids.mapped("product_id")
        boms_by_product = self.env["mrp.bom"]._bom_find(products=products)

        grouped_demand: dict[ProductProduct, StockMove] = self.demand_move_ids.grouped(
            "product_id"
        )
        for product, moves in grouped_demand.items():
            bom = boms_by_product.get(product)
            demand_line = self.env["mrp.campaign.demand"].create(
                {
                    "campaign_id": campaign_id.id,
                    "product_id": product.id,
                    "bom_id": bom.id if bom else False,
                }
            )
            proxy_vals = [
                {
                    "demand_id": demand_line.id,
                    "move_id": move.id,
                    "promised_qty": move.product_uom_qty,
                }
                for move in moves
            ]
            self.env["mrp.campaign.demand.proxy"].create(proxy_vals)

        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "views": [[False, "form"]],
            "res_id": campaign_id.id,
            "target": "current",
        }
