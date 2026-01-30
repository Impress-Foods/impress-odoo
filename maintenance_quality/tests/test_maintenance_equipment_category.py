import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestMaintenanceEquipmentCategory(TransactionCase):
    def setUp(self):
        super().setUp()
        self.category_model = self.env["maintenance.equipment.category"]
        self.qcp_model = self.env["quality.point"]

        self.category = self.category_model.create(
            {
                "name": "Test Category",
            }
        )

        self.qcp = self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_category_ids": [(4, self.category.id)],
            }
        )

    def test_compute_quality_point_count_category(self):
        self.assertEqual(self.category.quality_point_count, 1)
