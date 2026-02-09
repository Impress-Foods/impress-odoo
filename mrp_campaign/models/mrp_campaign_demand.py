from datetime import datetime, time

from odoo import _, fields, models
from odoo.exceptions import UserError


class MrpCampaignDemand(models.Model):
    _name = "mrp.campaign.demand"
    _description = "Manufacturing Campaign Demand Line"

    campaign_id = fields.Many2one(
        "mrp.campaign", string="Campaign", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id"
    )
    qty = fields.Float(compute="_compute_qty")

    move_dest_ids = fields.Many2many(
        "stock.move",
        string="Destination Moves",
        help="Moves that this production will fulfill.",
    )
    product_uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )
    component_uom_id = fields.Many2one(
        string="Component UoM", related="campaign_id.product_id.product_tmpl_id.uom_id"
    )

    production_id = fields.Many2one("mrp.production", ondelete="set null")

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Bill of Materials",
        help="The specific BoM to be used for manufacturing the product on this line.",
    )

    def _compute_qty(self):
        for rec in self:
            rec.qty = sum(rec.move_dest_ids.mapped("product_uom_qty"))

    def _create_finished_product_mo(self, confirm=True):
        """
        Creates a manufacturing order for the finished product of this line
        and links it to the campaign and original demand moves.
        """
        self.ensure_one()
        if not self.bom_id:
            raise UserError(
                _(
                    (
                        "Cannot create Manufacturing Order for line"
                        "with product %s because it is missing a Bill of Materials."
                    ),
                    self.product_id.display_name,
                )
            )

        mo = self.env["mrp.production"].create(
            {
                "product_id": self.product_id.id,
                "bom_id": self.bom_id.id,
                "product_qty": self.product_demand_qty,
                "product_uom_id": self.product_uom_id.id,
                "origin": self.campaign_id.name,
                "date_start": datetime.combine(
                    self.campaign_id.date_planned_start, time(13, 0)
                ),
                "date_deadline": datetime.combine(
                    self.campaign_id.date_planned_start, time(23, 0)
                ),
                "campaign_id": self.campaign_id.id,  # Link as a consumer
                "created_by_campaign": True,
            }
        )

        if self.move_dest_ids:
            # Link the original SO moves to this consolidated MO for traceability
            self.move_dest_ids.write({"created_production_id": mo.id})

        if confirm:
            mo.action_confirm()
        self.production_id = mo

        if mo.move_finished_ids:
            mo.move_finished_ids.write(
                {"move_dest_ids": [(6, 0, self.move_dest_ids.ids)]}
            )

        return mo
