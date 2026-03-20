import json

from odoo import api, fields, models


class MrpCampaignCreator(models.AbstractModel):
    _name = "mrp.campaign.creator"
    _description = "Abstract base wizard - bridges provide concrete implementation"

    product_id = fields.Many2one(
        comodel_name="product.product",
        domain="[('product_tmpl_id.is_campaign_anchor', '=', True)]",
    )
    planned_date = fields.Date()
    campaign_id = fields.Many2one("mrp.campaign")

    available_lines = fields.Char(
        help="JSON array of demand lines. Fields: id, name, qty, date, additional_ref",
    )
    selected_line_ids = fields.Char(
        help="JSON array of selected line IDs",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.available_lines = json.dumps(self._get_available_lines(self.product_id.id))
        self.selected_line_ids = "[]"

    def _get_available_lines(self, product_id) -> list[dict]:
        return []

    def _get_valid_sources(self):
        return (
            self.env[self._source_model] if hasattr(self, "_source_model") else self.env
        )

    def _get_selected_sources(self):
        selected_ids = json.loads(self.selected_line_ids or "[]")
        return self._get_valid_sources().filtered(lambda r: r.id in selected_ids)

    def _create_demands(self, campaign) -> None:
        raise NotImplementedError(
            "Bridge must implement _create_demands(campaign) to populate demands."
        )

    def process_wizard(self) -> dict | None:
        pass
