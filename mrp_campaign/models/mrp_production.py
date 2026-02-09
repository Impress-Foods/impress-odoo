import logging

from odoo import api, fields, models

from odoo.addons.mrp.models.mrp_production import MrpProduction

_logger = logging.getLogger(__name__)


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    anchor_product_id = fields.Many2one(
        "product.product", compute="_compute_anchor_product_id", store=True
    )

    campaign_id = fields.Many2one(related="campaign_line_id.campaign_id")

    campaign_product_qty = fields.Float(
        compute="_compute_campaign_product_qty",
        store=True,
        help="If this is a consumer MO, this field shows the quantity of the "
        "campaign's intermediate product that this order consumes.",
    )

    campaign_color = fields.Char(
        related="campaign_id.campaign_color",
    )
    campaign_sequence = fields.Integer(
        string="Campaign Sequence",
        related="campaign_id.sequence",
        store=True,
        readonly=True,
        help="Sequence of the parent campaign",
    )

    created_by_campaign = fields.Boolean()
    campaign_line_id = fields.Many2one("mrp.campaign.line")

    def write(self, vals):
        res = super().write(vals)

        if "lot_producing_id" in vals and not self.env.context.get("syncing_lot"):
            lot_id = vals.get("lot_producing_id")
            if lot_id:
                lot = self.env["stock.lot"].browse(lot_id)
                for production in self:
                    if production.campaign_id:
                        production.campaign_id._sync_lot_on_productions(
                            lot.name, productions_to_skip=production
                        )

        return res

    @api.depends("move_raw_ids.product_uom_qty", "move_raw_ids.state")
    def _compute_campaign_product_qty(self):
        """
        Computes the total quantity of a campaign's specific intermediate product
        that is consumed by this manufacturing order.
        """
        for mo in self:
            if not mo.campaign_id:
                mo.campaign_product_qty = 0.0
                continue

            campaign_product = mo.campaign_id.product_id
            # Filter the raw moves to find the ones for the campaign's product
            # that are not cancelled and sum their quantities.
            moves = mo.move_raw_ids.filtered(
                lambda m, product=campaign_product: (
                    m.product_id == product and m.state != "cancel"
                )
            )
            mo.campaign_product_qty = sum(moves.mapped("product_uom_qty"))

    def _split_productions(
        self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False
    ):
        res = super()._split_productions(
            amounts=amounts,
            cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty,
        )
        for rec in self:
            bos = rec.procurement_group_id.mrp_production_ids
            for bo in bos:
                bo.lot_producing_id = rec.lot_producing_id
        return res

    def _compute_anchor_product_id(self) -> None:
        for rec in self:
            if rec.product_id:
                rec.anchor_product_id = rec.product_id.anchor_product_id
            else:
                rec.anchor_product_id = self.env["product.product"]

    def action_confirm(self: MrpProduction):
        rec = super().action_confirm()
        # self.action_assign_all()
        return rec

    def action_view_campaign(self):
        self.ensure_one()
        if not self.campaign_id:
            return
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "res_id": self.campaign_id.id,
            "view_mode": "form",
            "target": "current",
        }
