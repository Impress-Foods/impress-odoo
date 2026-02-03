import logging

from odoo import api, fields, models

from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.stock.models.stock_move import StockMove

from ..models.mrp_campaign import MrpCampaign

_logger = logging.getLogger(__name__)


class MrpCampaignCreator(models.TransientModel):
    _name = "mrp.campaign.creator"
    _description = "Wizard to help the creation of MRP Campaigns"

    product_id = fields.Many2one(
        comodel_name="product.product",
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
        string="Anchor Product",
    )
    planned_date = fields.Date()

    demand_move_ids = fields.Many2many(
        "stock.move", relation="mrp_campaign_creator_actual"
    )
    valid_demand_move_ids = fields.Many2many(
        "stock.move",
        relation="mrp_campaign_creator_valid",
        compute="_compute_valid_demand_move_ids",
    )

    @api.depends("product_id")
    def _compute_valid_demand_move_ids(self):
        for rec in self:
            if not rec.product_id:
                rec.valid_demand_move_ids = False
                return

            anchor_product = rec.product_id

            # Find all products that use this anchor, by traversing BoMs upwards
            all_descendants = self.env["product.product"].browse(anchor_product.id)
            products_to_check = self.env["product.product"].browse(anchor_product.id)

            while products_to_check:
                # Find boms where products_to_check are components
                boms = (
                    self.env["mrp.bom.line"]
                    .search([("product_id", "in", products_to_check.ids)])
                    .mapped("bom_id")
                )

                # Find finished goods for these boms
                parent_products = boms.mapped("product_id")
                parent_from_template = boms.mapped("product_tmpl_id").mapped(
                    "product_variant_ids"
                )

                all_parents = parent_products | parent_from_template

                # Find new products we haven't seen before to avoid infinite loops
                newly_found = all_parents - all_descendants

                if not newly_found:
                    break

                all_descendants |= newly_found
                products_to_check = newly_found

            # Now search for moves for these products.
            domain = [
                (
                    "state",
                    "in",
                    [
                        "draft",
                        "waiting",
                        "confirmed",
                        "partially_available",
                        "assigned",
                    ],
                ),
                ("product_id", "in", all_descendants.ids),
            ]
            rec.valid_demand_move_ids = self.env["stock.move"].search(domain)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.make_campaign()
        return res

    def make_campaign(self):
        self.ensure_one()
        values = {
            "date_planned_start": self.planned_date,
            "product_id": self.product_id.id,
        }
        campaign_id: MrpCampaign = self.env["mrp.campaign"].create([values])
        line_values: list[dict] = []

        products = self.demand_move_ids.mapped("product_id")
        boms_by_product = self.env["mrp.bom"]._bom_find(products=products)

        grouped_demand: dict[ProductProduct, StockMove] = self.demand_move_ids.grouped(
            "product_id"
        )
        for product, moves in grouped_demand.items():
            bom = boms_by_product.get(product)
            line_values.append(
                {
                    "campaign_id": campaign_id.id,
                    "product_id": product.id,
                    "move_dest_ids": moves.ids,
                    "bom_id": bom.id if bom else False,
                }
            )
        self.env["mrp.campaign.line"].create(line_values)
