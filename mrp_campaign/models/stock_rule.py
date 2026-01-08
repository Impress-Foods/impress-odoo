from odoo import api, models

from odoo.addons.stock.models.stock_rule import StockRule

from .procurement import Procurement


class StockRuleInherit(models.Model):
    _inherit = "stock.rule"

    @api.model
    def _run_manufacture(self, procurements: list[tuple[Procurement, StockRule]]):
        standard_procurements = []
        campaign_procurements = []

        for procurement, rule in procurements:
            if procurement.product_id.is_campaign_manufactured:
                campaign_procurements.append((procurement, rule))
            else:
                standard_procurements.append((procurement, rule))
        if standard_procurements:
            super()._run_manufacture(standard_procurements)

        if campaign_procurements:
            self.env["mrp.campaign"]._collect_procurements(campaign_procurements)
        return True
