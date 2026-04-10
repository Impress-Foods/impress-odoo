from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command

from odoo.addons.mrp.models.mrp_production import MrpProduction


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
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

    source_model = fields.Char("Source Document Model", index=True)
    source_id = fields.Integer("Source Document ID", index=True)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_campaign(self) -> dict:
        self.ensure_one()
        if not self.campaign_id:
            return {}
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "res_id": self.campaign_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_source(self) -> dict:
        if self.source_model and self.source_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": self.source_model,
                "res_id": self.source_id,
                "view_mode": "form",
                "target": "new",
            }
        return {}

    # -------------------------------------------------------------------------
    # BUSINESS LOGIC
    # -------------------------------------------------------------------------
    def _split_productions(
        self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False
    ) -> MrpProduction:
        res: MrpProduction = super()._split_productions(
            amounts=amounts,
            cancel_remaining_qty=cancel_remaining_qty,
            set_consumed_qty=set_consumed_qty,
        )
        if self.lot_producing_ids:
            res.with_context(syncing_lot=True).write(
                {"lot_producing_ids": [Command.link(self.lot_producing_ids[:1].id)]}
            )
        if self.campaign_line_id:
            res.write({"campaign_line_id": self.campaign_line_id.id})

        return res

    @api.constrains("lot_producing_ids")
    def _check_single_lot_for_campaign(self):
        for mo in self.filtered("campaign_id"):
            if len(mo.lot_producing_ids) > 1:
                raise ValidationError(
                    self.env._("Campaign MOs cannot have multiple lots.")
                )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def write(self, vals) -> bool:
        res = super().write(vals)

        if "lot_producing_ids" in vals and not self.env.context.get("syncing_lot"):
            lots = self.lot_producing_ids[:1]
            if lots:
                campaigns = self.mapped("campaign_id")
                for campaign in campaigns:
                    if campaign.lot_name != lots.name:
                        campaign.write({"lot_name": lots.name})

        return res
