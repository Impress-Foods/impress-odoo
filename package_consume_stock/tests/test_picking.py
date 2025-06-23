from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestStockPicking(TransactionCase):
    def setUp(self):
        super().setUp()
