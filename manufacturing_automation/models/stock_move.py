from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    demanded_by_campaign_id = fields.Many2one(
        "mrp.campaign",
        string="Demanded by Campaign",
        copy=False,
        index=True,
        help="The mrp campaign that is creating demand for this specific move.",
    )

    def write(self, vals):
        """
        Overrides the standard write method to manually trigger the linking of
        consumer Manufacturing Orders (MOs) to their associated campaign.

        This custom logic is necessary because the default Odoo ORM dependency
        tracking for computed fields proved unreliable in this complex transactional
        workflow (i.e., when stock moves are created and linked to campaigns
        as part of a larger MO confirmation process).

        When 'demanded_by_campaign_id' or 'raw_material_production_id' is changed
        on a stock move, this method identifie
        all affected MOs (before and after the change)
        and explicitly sets their 'associated_campaign_id' field.
        """
        # Capture production orders linked to these moves BEFORE the write operation.
        productions_before = self.mapped("raw_material_production_id")

        res = super().write(vals)

        # If the campaign link or the production link of these moves has changed,
        # we need to ensure the associated MOs are updated.
        if "demanded_by_campaign_id" in vals or "raw_material_production_id" in vals:
            # Capture production orders linked to these moves AFTER the write operation.
            # Combine 'before' and 'after' to catch all potentially affected MOs.
            all_productions = productions_before | self.mapped(
                "raw_material_production_id"
            )

            for production in all_productions:
                # Determine the correct campaign for the production based on its type.
                # If it's a provider MO (has campaign_id), use that.
                # If it's a consumer MO, find the campaign
                # through its raw material moves.
                campaign_to_set = False
                if production.campaign_id:
                    campaign_to_set = production.campaign_id
                else:
                    campaigns = production.move_raw_ids.mapped(
                        "demanded_by_campaign_id"
                    )
                    campaign_to_set = fields.first(campaigns)

                # Update the associated_campaign_id field only if it needs changing,
                # to prevent unnecessary writes and potential recursion issues.
                if production.associated_campaign_id != campaign_to_set:
                    production.associated_campaign_id = campaign_to_set

        return res
