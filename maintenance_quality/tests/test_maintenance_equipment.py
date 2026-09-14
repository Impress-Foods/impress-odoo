import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestMaintenanceEquipment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.equipment_model = cls.env["maintenance.equipment"]
        cls.equipment_category_model = cls.env["maintenance.equipment.category"]
        cls.workcenter_model = cls.env["mrp.workcenter"]
        cls.qcp_model = cls.env["quality.point"]

        cls.category = cls.equipment_category_model.create(
            {
                "name": "Test Category",
            }
        )

        cls.workcenter = cls.workcenter_model.create(
            {
                "name": "Test Workcenter",
            }
        )

        cls.qcp_category = cls.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_category_ids": [(4, cls.category.id)],
            }
        )

        cls.qcp_workcenter = cls.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "workcenter_ids": [(4, cls.workcenter.id)],
            }
        )

    def test_compute_quality_point_count_equipment(self):
        equipment = self.equipment_model.create(
            {
                "name": "Test Equipment",
            }
        )

        self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_ids": [(4, equipment.id)],
            }
        )

        self.assertEqual(equipment.quality_point_count, 1)

    def test_compute_quality_point_count_equipment_cat(self):
        equipment = self.equipment_model.create(
            {
                "name": "Test Equipment",
                "category_id": self.category.id,
            }
        )

        self.assertEqual(equipment.quality_point_count, 1)

    def test_compute_quality_point_count_workcenter(self):
        equipment = self.equipment_model.create(
            {
                "name": "Test Equipment",
                "workcenter_id": self.workcenter.id,
            }
        )

        self.assertEqual(equipment.quality_point_count, 1)

    def test_compute_quality_point_count_category_and_workcenter(self):
        equipment = self.equipment_model.create(
            {
                "name": "Test Equipment",
                "category_id": self.category.id,
                "workcenter_id": self.workcenter.id,
            }
        )

        self.assertEqual(equipment.quality_point_count, 2)

    def test_compute_quality_point_count_equipment_category_and_workcenter(self):
        equipment = self.equipment_model.create(
            {
                "name": "Test Equipment",
                "category_id": self.category.id,
                "workcenter_id": self.workcenter.id,
            }
        )
        self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_ids": [(4, equipment.id)],
            }
        )

        self.assertEqual(equipment.quality_point_count, 3)
