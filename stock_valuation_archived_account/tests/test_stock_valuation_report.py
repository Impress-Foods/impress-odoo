from odoo.addons.stock_account.tests.common import TestStockValuationCommon


class TestStockValuationArchivedAccount(TestStockValuationCommon):
    """Regression tests for the archived-account crash in the Stock Valuation
    report (controller.js:50 / stock_valuation_report.py:130).

    The base ``_get_report_data`` fetches accounts via ``search_read`` which
    applies ``active_test=True``; an archived account referenced in
    ``lines_by_account_id`` is therefore absent from ``accounts_by_id`` and
    the JS client crashes. The override backfills such ids with
    ``active_test=False``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Dedicated valuation account on a dedicated category, so archiving it
        # never touches the company-wide default account used by other tests.
        # No company_id: in v19 account.account has no such field; the company
        # is taken from the env (already scoped to cls.company by the parent).
        cls.archived_valuation_account = cls.env["account.account"].create(
            {
                "name": "Archivable Stock Valuation",
                "code": "XVAL999",
                "account_type": "asset_current",
            }
        )
        cls.category_archived = cls.env["product.category"].create(
            {
                "name": "Archivable Valuation Category",
                "property_valuation": "real_time",
                "property_cost_method": "standard",
                "property_stock_valuation_account_id": (
                    cls.archived_valuation_account.id
                ),
            }
        )
        cls.product_archived = cls.env["product.product"].create(
            {
                "name": "Archivable Valuation Product",
                "categ_id": cls.category_archived.id,
                "is_storable": True,
                "standard_price": 10.0,
                "uom_id": cls.uom.id,
            }
        )

    def _report_values(self):
        return self.env["stock_account.stock.valuation.report"].get_report_values(
            date=False
        )

    def test_baseline_all_active_accounts_resolved(self) -> None:
        """Happy path: no account archived, backfill is a no-op and every
        referenced id is present in ``accounts_by_id``."""
        self._make_in_move(self.product_archived, 10, unit_cost=10)
        values = self._report_values()
        accounts_by_id = values["data"]["accounts_by_id"]
        for section in ("initial_balance", "ending_stock"):
            for account_id in values["data"][section]["lines_by_account_id"]:
                self.assertIn(int(account_id), accounts_by_id)
        self.assertIn(self.archived_valuation_account.id, accounts_by_id)

    def test_archived_account_is_backfilled(self) -> None:
        """Edge case: archiving the valuation account must NOT crash the
        report and the archived id must still resolve in ``accounts_by_id``."""
        self._make_in_move(self.product_archived, 10, unit_cost=10)
        self.archived_valuation_account.active = False
        # Without the fix the next line raises in the initial_balance loop
        # because accounts_by_id no longer contains the archived id.
        values = self._report_values()
        accounts_by_id = values["data"]["accounts_by_id"]
        self.assertIn(
            self.archived_valuation_account.id,
            accounts_by_id,
            "Archived valuation account was not backfilled into accounts_by_id.",
        )
        self.assertEqual(
            accounts_by_id[self.archived_valuation_account.id]["display_name"],
            self.archived_valuation_account.display_name,
        )
