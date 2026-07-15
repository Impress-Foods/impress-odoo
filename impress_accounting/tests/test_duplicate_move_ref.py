from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestDuplicateMoveRef(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create({"name": "Partner A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Partner B"})

        cls.account_expense = cls.env["account.account"].create(
            {
                "name": "Test Expense",
                "code": "99999901",
                "account_type": "expense_direct_cost",
            }
        )
        cls.account_payable = cls.env["account.account"].create(
            {
                "name": "Test Payable",
                "code": "88888801",
                "account_type": "liability_payable",
                "reconcile": True,
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Vendor Bills",
                "type": "purchase",
                "code": "VBJ",
            }
        )
        cls.journal.default_account_id = cls.account_expense
        cls.partner_a.property_account_payable_id = cls.account_payable

    def _create_vendor_bill(self, partner, ref):
        return self.env["account.move"].create(
            {
                "partner_id": partner.id,
                "ref": ref,
                "journal_id": self.journal.id,
                "move_type": "in_invoice",
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (0, 0, {"name": "Line", "price_unit": 100.0, "quantity": 1})
                ],
            }
        )

    def _create_entry(self, partner, ref):
        return self.env["account.move"].create(
            {
                "partner_id": partner.id,
                "ref": ref,
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "account_id": self.account_expense.id,
                            "debit": 100,
                            "credit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Counterpart",
                            "account_id": self.account_payable.id,
                            "debit": 0,
                            "credit": 100,
                        },
                    ),
                ],
            }
        )

    def test_unique_pair_posts(self):
        """Distinct (partner, ref) pairs should post without error."""
        move_a = self._create_vendor_bill(self.partner_a, "INV-001")
        move_b = self._create_vendor_bill(self.partner_b, "INV-002")
        moves = move_a | move_b
        moves.action_post()
        self.assertEqual(moves.mapped("state"), ["posted", "posted"])

    def test_same_ref_different_partner_posts(self):
        """Same ref with different partners should post."""
        move_a = self._create_vendor_bill(self.partner_a, "INV-001")
        move_b = self._create_vendor_bill(self.partner_b, "INV-001")
        moves = move_a | move_b
        moves.action_post()
        self.assertEqual(moves.mapped("state"), ["posted", "posted"])

    def test_ref_match_raises(self):
        """Posting a vendor bill with same info as an existing posted bill fails."""
        self._create_vendor_bill(self.partner_a, "INV-001").action_post()
        dup = self._create_vendor_bill(self.partner_a, "INV-001")
        with self.assertRaises(UserError):
            dup.action_post()

    def test_move_does_not_match_itself(self):
        """A move should not match itself when posted alone."""
        move = self._create_vendor_bill(self.partner_a, "INV-001")
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_no_ref_skipped(self):
        """Moves without a ref should be skipped and post normally."""
        move_a = self._create_vendor_bill(self.partner_a, False)
        move_b = self._create_vendor_bill(self.partner_a, False)
        (move_a | move_b).action_post()
        self.assertEqual(move_a.state, "posted")
        self.assertEqual(move_b.state, "posted")

    def test_no_partner_skipped(self):
        """Moves without a partner should be skipped and post normally."""
        move_a = self._create_vendor_bill(self.partner_a, "INV-001")
        move_b = self._create_entry(self.env["res.partner"], "INV-001")
        move_a.action_post()
        move_b.action_post()
        self.assertEqual(move_a.state, "posted")
        self.assertEqual(move_b.state, "posted")

    def test_ref_differs_does_not_raise(self):
        """Same partner but different refs should post."""
        move_a = self._create_vendor_bill(self.partner_a, "INV-001")
        move_b = self._create_vendor_bill(self.partner_a, "INV-002")
        move_a.action_post()
        move_b.action_post()
        self.assertEqual(move_a.state, "posted")
        self.assertEqual(move_b.state, "posted")

    def test_ref_match_with_parent_partner(self):
        """Bill for a child partner conflicts with one for parent with same ref."""
        parent = self.env["res.partner"].create({"name": "Parent Corp"})
        child = self.env["res.partner"].create(
            {"name": "Child", "parent_id": parent.id}
        )
        parent.property_account_payable_id = self.account_payable
        child.property_account_payable_id = self.account_payable
        self._create_vendor_bill(child, "INV-001").action_post()
        with self.assertRaises(UserError):
            self._create_vendor_bill(parent, "INV-001").action_post()

    def test_ref_match_with_parent_partner_reverse(self):
        """Bill for parent partner conflicts with one for the child with same ref."""
        parent = self.env["res.partner"].create({"name": "Parent Corp"})
        child = self.env["res.partner"].create(
            {"name": "Child", "parent_id": parent.id}
        )
        parent.property_account_payable_id = self.account_payable
        child.property_account_payable_id = self.account_payable
        self._create_vendor_bill(parent, "INV-001").action_post()
        with self.assertRaises(UserError):
            self._create_vendor_bill(child, "INV-001").action_post()

    def test_mixed_batch_with_dupe_raises(self):
        """Batch of 3 where 2 conflict should fail entirely."""
        move_a = self._create_vendor_bill(self.partner_a, "INV-001")
        move_b = self._create_vendor_bill(self.partner_b, "INV-002")
        move_c = self._create_vendor_bill(self.partner_a, "INV-001")
        with self.assertRaises(UserError):
            (move_a | move_b | move_c).action_post()
        self.assertEqual(move_a.state, "draft")
        self.assertEqual(move_b.state, "draft")
        self.assertEqual(move_c.state, "draft")

    def test_non_in_invoice_not_checked(self):
        """Non-in_invoice moves with same (partner, ref) should not be blocked."""
        move_a = self._create_entry(self.partner_a, "INV-001")
        move_b = self._create_entry(self.partner_a, "INV-001")
        move_a.action_post()
        move_b.action_post()
        self.assertEqual(move_a.state, "posted")
        self.assertEqual(move_b.state, "posted")
