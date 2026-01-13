import logging
from datetime import timedelta

from odoo import api, models

from odoo.addons.stock.models.stock_rule import StockRule

from .procurement import Procurement

_logger = logging.getLogger(__name__)


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

    def _get_lead_days(self, product, **values) -> tuple[dict, dict]:
        delays, delay_description = super()._get_lead_days(product, **values)
        if values.get("visibility_days", False):
            delays["visibility_days"] = values["visibility_days"]
            delays["total_delay"] += values["visibility_days"]
            delay_description.append(
                ("Visibility Days", f"+ {int(values['visibility_days'])} day(s)")
            )
        return delays, delay_description


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _get_lead_days_values(self):
        self.ensure_one()
        rec = super()._get_lead_days_values()
        if self.visibility_days != 0:
            rec["visibility_days"] = self.visibility_days
        return rec

    def _get_orderpoint_procurement_date(self):
        res = super()._get_orderpoint_procurement_date()
        # Remove the visibility days added to leadtime
        res -= timedelta(days=self.visibility_days)
        return res
