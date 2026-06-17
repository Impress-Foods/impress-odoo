from odoo import api, models


class StockValuationReport(models.AbstractModel):
    """Extend the Stock Valuation report to backfill accounts that the base
    ``_get_report_data`` drops.

    Base behavior: ``account.account.search_read`` at
    ``stock_valuation_report.py:130`` uses the default ``active_test=True``
    context, so any *archived* account referenced in
    ``lines_by_account_id`` (initial balance / ending stock) or in the
    inventory-loss / stock-variation lines is silently omitted from
    ``accounts_by_id``. The JS controller then reads
    ``accounts_by_id[accountId]`` and crashes with
    ``can't access property "display_name", account is undefined``
    on ``controller.js:50`` (the ``initial_balance`` loop, which lacks the
    optional chaining present on the ``ending_stock`` loop).

    This override re-fetches the missing ids with ``active_test=False`` and
    merges them into ``accounts_by_id`` so every referenced id resolves.
    """

    _inherit = "stock_account.stock.valuation.report"

    @api.model
    def _get_report_data(self, date=False, product_category=False, warehouse=False):
        report_data = super()._get_report_data(
            date=date, product_category=product_category, warehouse=warehouse
        )
        accounts_by_id = report_data["accounts_by_id"]
        referenced_ids: set[int] = set()
        for section in ("initial_balance", "ending_stock"):
            referenced_ids.update(report_data[section]["lines_by_account_id"].keys())
        if report_data.get("inventory_loss"):
            referenced_ids.update(
                line["account_id"] for line in report_data["inventory_loss"]["lines"]
            )
        referenced_ids.update(
            line["account_id"] for line in report_data["stock_variation"]["lines"]
        )
        missing_ids = [
            int(account_id)
            for account_id in referenced_ids
            if int(account_id) not in accounts_by_id
        ]
        if missing_ids:
            missing_data = (
                self.env["account.account"]
                .with_context(active_test=False)
                .search_read(
                    [("id", "in", missing_ids)],
                    ["id", "name", "code", "display_name"],
                )
            )
            for account_data in missing_data:
                accounts_by_id[account_data["id"]] = account_data
        return report_data
