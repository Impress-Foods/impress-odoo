from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestMaintenanceRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.request_model = cls.env["maintenance.request"]

        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
            }
        )

        cls.equipment = cls.env["maintenance.equipment"].create(
            {"name": "Test equipment"}
        )
        cls.scrap = cls.env["stock.scrap"]

    @classmethod
    def _create_scrap(cls, request, qty: float = 10):
        return cls.scrap.create(
            {
                "maintenance_request_id": request.id,
                "product_id": cls.product.id,
                "scrap_qty": qty,
            }
        )

    def test_create_scrap(self):
        request = self.request_model.create(
            {"name": "Test Request", "equipment_id": self.equipment.id}
        )

        scrap_id = self._create_scrap(request)
        self.assertEqual(len(request.scrap_ids), 1)
        self.assertEqual(scrap_id.maintenance_request_id.id, request.id)

    def test_delete_draft_scrap(self):
        request = self.request_model.create(
            {
                "name": "Test Request",
                "equipment_id": self.equipment.id,
            }
        )
        scrap_move = self._create_scrap(request)

        scrap_move.unlink()
        self.assertEqual(len(request.scrap_ids), 0)

    def test_delete_done_scrap(self):
        request = self.request_model.create(
            {"name": "Test Request", "equipment_id": self.equipment.id}
        )
        scrap_move = self._create_scrap(request)
        scrap_move.do_scrap()

        with self.assertRaises(UserError):
            scrap_move.unlink()

    def test_delete_request_with_draft_scrap(self):
        request = self.request_model.create(
            {"name": "Test Request", "equipment_id": self.equipment.id}
        )
        self._create_scrap(request)

        count_before = self.env["stock.scrap"].search_count(
            [("product_id", "=", self.product.id)]
        )

        request.unlink()
        count_after = self.env["stock.scrap"].search_count(
            [("product_id", "=", self.product.id)]
        )

        self.assertEqual(1, count_before)
        self.assertEqual(0, count_after)

    def test_delete_request_with_done_scrap(self):
        request = self.request_model.create(
            {"name": "Test Request", "equipment_id": self.equipment.id}
        )
        scrap_move = self._create_scrap(request)
        scrap_move.do_scrap()

        with self.assertRaises(UserError):
            request.unlink()
