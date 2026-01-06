import logging

from odoo import api, fields, models

from odoo.addons.mrp.models.mrp_production import MrpProduction

_logger = logging.getLogger(__name__)


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Campaign",
        ondelete="restrict",
        help="The campaign that created this manufacturing order (provider MO).",
    )

    associated_campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Associated Campaign",
        copy=False,
        index=True,
        help="The campaign this manufacturing order is linked to, either as a "
        "provider (set directly) or as a consumer (set via stock moves).",
    )

    campaign_product_qty = fields.Float(
        compute="_compute_campaign_product_qty",
        store=True,
        help="If this is a consumer MO, this field shows the quantity of the "
        "campaign's intermediate product that this order consumes.",
    )

    campaign_color = fields.Char(
        related="associated_campaign_id.campaign_color",
        string="Campaign Color",
    )

    def write(self, vals):
        res = super().write(vals)
        # Only trigger if lot_producing_id is changed and we aren't already syncing
        if (
            "lot_producing_id" in vals
            and vals["lot_producing_id"]
            and not self.env.context.get("skip_campaign_sync")
        ):
            for mo in self.filtered(lambda m: m.associated_campaign_id):
                mo.associated_campaign_id._sync_campaign_lots(mo.lot_producing_id)
        return res

    @api.depends(
        "associated_campaign_id", "move_raw_ids.product_uom_qty", "move_raw_ids.state"
    )
    def _compute_campaign_product_qty(self):
        """
        Computes the total quantity of a campaign's specific intermediate product
        that is consumed by this manufacturing order.
        """
        for mo in self:
            if not mo.associated_campaign_id:
                mo.campaign_product_qty = 0.0
                continue

            campaign_product = mo.associated_campaign_id.product_id
            # Filter the raw moves to find the ones for the campaign's product
            # that are not cancelled and sum their quantities.
            moves = mo.move_raw_ids.filtered(
                lambda m, product=campaign_product: m.product_id == product
                and m.state != "cancel"
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

    def action_confirm(self: MrpProduction):
        rec = super().action_confirm()
        self.action_assign_all()
        return rec

    def action_view_campaign(self):
        self.ensure_one()
        if not self.associated_campaign_id:
            return
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.campaign",
            "res_id": self.associated_campaign_id.id,
            "view_mode": "form",
            "target": "current",
        }
