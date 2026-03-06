from odoo.tests.common import TransactionCase


class TestTest(TransactionCase):
    def test_duplicate(self) -> None:
        test = self.env["misc.test"].create({})

        self.assertTrue(test.sequence)

        duplicate = test.copy()

        self.assertTrue(duplicate.sequence)
        self.assertNotEqual(test.sequence, duplicate.sequence)
