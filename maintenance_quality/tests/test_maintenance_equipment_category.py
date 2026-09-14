import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestMaintenanceEquipmentCategory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category_model = cls.env["maintenance.equipment.category"]
        cls.qcp_model = cls.env["quality.point"]

        cls.category = cls.category_model.create(
            {
                "name": "Test Category",
            }
        )

        cls.qcp = cls.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_category_ids": [(4, cls.category.id)],
            }
        )

    def test_compute_quality_point_count_category(self):
        self.assertEqual(self.category.quality_point_count, 1)
