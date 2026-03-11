from odoo import fields, models

from odoo.addons.mrp.models.mrp_production import MrpProduction


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

    def write(self, vals) -> bool:
        res = super().write(vals)

        if "lot_producing_id" in vals and not self.env.context.get("syncing_lot"):
            lot_id = vals.get("lot_producing_id")
            if lot_id:
                lot = self.env["stock.lot"].browse(lot_id)
                campaigns = self.mapped("campaign_id")
                for campaign in campaigns:
                    if campaign.lot_name != lot.name:
                        campaign.write({"lot_name": lot.name})

        return res

    def _split_productions(
        self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False
    ) -> MrpProduction:
        res: MrpProduction = super()._split_productions(
            amounts=amounts,
            cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty,
        )
        if self.lot_producing_id:
            res.with_context(syncing_lot=True).write(
                {"lot_producing_id": self.lot_producing_id.id}
            )
        if self.campaign_line_id:
            res.write({"campaign_line_id": self.campaign_line_id.id})

        return res

    def action_view_campaign(self) -> dict:  # pragma: no cover
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
