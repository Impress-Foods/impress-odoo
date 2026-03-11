from datetime import timedelta

from odoo import models


class StockRuleInherit(models.Model):
    _inherit = "stock.rule"

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
