import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductionOrder(models.Model):
    _inherit = "mrp.production"

    campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Campaign",
        ondelete="restrict",
    )

    associated_campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Associated Campaign",
        compute="_compute_associated_campaign_id",
        store=False,
    )

    campaign_product_qty = fields.Float(compute="_compute_associated_campaign_id")
    campaign_color = fields.Char(compute="_compute_associated_campaign_id")

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

    @api.depends("campaign_id", "move_raw_ids")
    def _compute_associated_campaign_id(self):
        for mo in self:
            if mo.campaign_id:
                mo.associated_campaign_id = mo.campaign_id

            else:
                campaign = self.env["mrp.campaign"].search(
                    [("demand_move_ids", "in", mo.move_raw_ids.ids)], limit=1
                )
                mo.associated_campaign_id = campaign

            if mo.associated_campaign_id:
                mo.campaign_color = mo.associated_campaign_id.color
                product = mo.associated_campaign_id.product_id
                move = mo.move_raw_ids.filtered_domain(
                    [("product_id", "=", product.id)]
                )
                mo.campaign_product_qty = move.product_uom_qty

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
