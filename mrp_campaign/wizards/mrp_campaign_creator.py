from odoo import fields, models


class MrpCampaignCreator(models.TransientModel):
    _name = "mrp.campaign.creator"
    _description = "Abstract base wizard - bridges provide concrete implementation"

    product_id = fields.Many2one(
        comodel_name="product.product",
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
        string="Anchor Product",
    )
    planned_date = fields.Date()
    campaign_id = fields.Many2one("mrp.campaign")

    def _create_demands(self, campaign) -> None:
        raise NotImplementedError(
            "Bridge must implement _create_demands(campaign) to populate demands."
        )

    def process_wizard(self) -> dict | None:
        pass
