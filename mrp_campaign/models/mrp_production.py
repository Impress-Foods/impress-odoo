import logging

from odoo import fields, models

from odoo.addons.mrp.models.mrp_production import MrpProduction

_logger = logging.getLogger(__name__)


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    anchor_product_id = fields.Many2one(related="product_id.anchor_product_id")

    campaign_id = fields.Many2one(related="campaign_line_id.campaign_id")

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

    def _split_productions(
        self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False
    ) -> MrpProduction:
        res: MrpProduction = super()._split_productions(
            amounts=amounts,
            cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty,
        )
        for rec in self:
            productions_to_update = res
            vals_to_write = {}
            if rec.lot_producing_id:
                vals_to_write["lot_producing_id"] = rec.lot_producing_id.id
            if rec.campaign_line_id:
                vals_to_write["campaign_line_id"] = rec.campaign_line_id.id
            if vals_to_write:
                productions_to_update.write(vals_to_write)

        return res

    def action_view_campaign(self):  # pragma: no cover
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
