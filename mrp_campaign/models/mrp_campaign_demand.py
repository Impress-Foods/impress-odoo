import logging

from odoo import api, fields, models

from .mrp_campaign_line import CampaignLine

_logger = logging.getLogger(__name__)


class MrpCampaignDemand(models.Model):
    _name = "mrp.campaign.demand"
    _description = "Manufacturing Campaign Demand Line"

    campaign_id = fields.Many2one("mrp.campaign", string="Campaign", ondelete="cascade")

    demand_proxy_ids = fields.One2many("mrp.campaign.demand.proxy", "demand_id")

    campaign_line_id = fields.Many2one("mrp.campaign.line")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id"
    )
    target_qty = fields.Float(
        string="Target Quantity",
        compute="_compute_target_qty",
        store=True,
    )

    move_ids = fields.Many2many(
        "stock.move",
        string="Destination Moves",
        help="Moves that this production will fulfill.",
        compute="_compute_move_ids",
        store=False,
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

    @api.depends("demand_proxy_ids.promised_qty")
    def _compute_target_qty(self) -> None:
        for rec in self:
            rec.target_qty = sum(rec.demand_proxy_ids.mapped("promised_qty"))

    @api.depends("demand_proxy_ids.move_id")
    def _compute_move_ids(self) -> None:
        for rec in self:
            rec.move_ids = rec.demand_proxy_ids.mapped("move_id")

    def create_campaign_line(self) -> CampaignLine:
        created_lines = self.env["mrp.campaign.line"]
        for rec in self:
            bom = (
                rec.bom_id
                or self.env["mrp.bom"]._bom_find(products=rec.product_id)[
                    rec.product_id
                ]
            )

            existing_line = rec.campaign_id.line_ids.filtered(
                lambda line, rec=rec, bom=bom: (
                    line.product_id == rec.product_id and line.bom_id == bom
                )
            )
            new_line = self.env["mrp.campaign.line"]

            if existing_line:
                existing_line.qty += rec.target_qty
                created_lines |= existing_line
            else:
                new_line = new_line.create(
                    {
                        "campaign_id": rec.campaign_id.id,
                        "product_id": rec.product_id.id,
                        "bom_id": bom.id,
                        "qty": rec.target_qty,
                    }
                )
                created_lines |= new_line

            rec.campaign_line_id = new_line or existing_line

        return created_lines


class MrpCampaignDemandProxy(models.Model):
    _name = "mrp.campaign.demand.proxy"
    _description = "Proxy between mrp.campaign.demand and stock.move"

    demand_id = fields.Many2one(
        "mrp.campaign.demand", required=True, ondelete="cascade"
    )
    move_id = fields.Many2one("stock.move", required=True, ondelete="cascade")
    upstream_qty = fields.Float(
        related="move_id.product_uom_qty", string="Upstream Demand"
    )
    promised_qty = fields.Float()
    campaign_id = fields.Many2one(related="demand_id.campaign_id")
    origin = fields.Char(related="move_id.origin")
