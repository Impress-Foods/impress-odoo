from odoo import Command
from odoo.tests import tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged("-at_install", "post_install")
class TestAnalyticPropagation(TestSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        plan = cls.env["account.analytic.plan"].create({"name": "Test Plan"})
        cls.analytic_account = cls.env["account.analytic.account"].create(
            {
                "name": "Test Analytic Account",
                "plan_id": plan.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.analytic_account_2 = cls.env["account.analytic.account"].create(
            {
                "name": "Test Analytic Account 2",
                "plan_id": plan.id,
                "company_id": cls.env.company.id,
            }
        )

        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner_a.id,
                "partner_invoice_id": cls.partner_a.id,
                "partner_shipping_id": cls.partner_a.id,
                "analytic_account_id": cls.analytic_account.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.company_data["product_order_no"].id,
                            "product_uom_qty": 1,
                            "tax_ids": False,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": cls.company_data["product_service_order"].id,
                            "product_uom_qty": 2,
                            "tax_ids": False,
                        }
                    ),
                ],
            }
        )
        cls.sol_1, cls.sol_2 = cls.sale_order.order_line

    def test_analytic_propagates_to_invoice_lines(self):
        """SO-level analytic_account_id should be in invoice line's analytic_distrib."""
        self.sale_order.action_confirm()
        invoice = self.sale_order._create_invoices()

        self.assertEqual(len(invoice.invoice_line_ids), 2)
        for inv_line in invoice.invoice_line_ids:
            expected = {str(self.analytic_account.id): 100}
            self.assertDictEqual(
                inv_line.analytic_distribution,
                expected,
                f"Invoice line {inv_line.id} missing the"
                " SO analytic account distribution",
            )

    def test_analytic_merges_with_line_distribution(self):
        """SO-level account merges additively with existing line-level distribution."""
        self.sol_1.analytic_distribution = {str(self.analytic_account_2.id): 50}
        self.sale_order.action_confirm()
        invoice = self.sale_order._create_invoices()

        sol_1_inv_line = invoice.invoice_line_ids.filtered(
            lambda line: line.sale_line_ids == self.sol_1
        )
        self.assertTrue(sol_1_inv_line)
        expected = {
            str(self.analytic_account_2.id): 50,
            str(self.analytic_account.id): 100,
        }
        self.assertDictEqual(
            sol_1_inv_line.analytic_distribution,
            expected,
            "Line-level and SO-level distributions should be merged",
        )

    def test_no_analytic_on_so(self):
        """No analytic_account_id on SO → no analytic_distribution on invoice lines."""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "partner_invoice_id": self.partner_a.id,
                "partner_shipping_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.company_data["product_order_no"].id,
                            "product_uom_qty": 1,
                            "tax_ids": False,
                        }
                    ),
                ],
            }
        )
        sale_order.action_confirm()
        invoice = sale_order._create_invoices()

        for inv_line in invoice.invoice_line_ids:
            self.assertFalse(
                inv_line.analytic_distribution,
                "No distribution expected when SO has no analytic_account_id",
            )

    def test_section_line_not_affected(self):
        """Display-type lines (sections/notes) should not get analytic distribution."""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "partner_invoice_id": self.partner_a.id,
                "partner_shipping_id": self.partner_a.id,
                "analytic_account_id": self.analytic_account.id,
                "order_line": [
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": "Test Section",
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.company_data["product_order_no"].id,
                            "product_uom_qty": 1,
                            "tax_ids": False,
                        }
                    ),
                ],
            }
        )
        sale_order.action_confirm()
        invoice = sale_order._create_invoices()

        for inv_line in invoice.invoice_line_ids:
            if inv_line.display_type in (
                "line_section",
                "line_subsection",
                "line_note",
            ):
                self.assertFalse(
                    inv_line.analytic_distribution,
                    "Section/note lines should not get analytic distribution",
                )
