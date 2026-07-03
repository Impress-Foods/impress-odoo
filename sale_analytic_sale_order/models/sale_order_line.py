from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        self._set_analytic_distribution(res, **optional_values)
        return res

    def _set_analytic_distribution(self, inv_line_vals, **optional_values):
        res = super()._set_analytic_distribution(inv_line_vals, **optional_values)
        order_account_id = self.order_id.analytic_account_id.id
        if order_account_id and not self.display_type:
            account_id_str = str(order_account_id)
            current_dist = inv_line_vals.get("analytic_distribution", {})
            current_dist[account_id_str] = current_dist.get(account_id_str, 0) + 100
            inv_line_vals["analytic_distribution"] = current_dist
        return res
