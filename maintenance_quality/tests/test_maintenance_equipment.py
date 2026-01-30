import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestMaintenanceEquipment(TransactionCase):
    def setUp(self):
        super().setUp()

        self.equipment_model = self.env["maintenance.equipment"]
        self.equipment_category_model = self.env["maintenance.equipment.category"]
        self.workcenter_model = self.env["mrp.workcenter"]
        self.qcp_model = self.env["quality.point"]

        self.category = self.equipment_category_model.create(
            {
                "name": "Test Category",
            }
        )

        self.workcenter = self.workcenter_model.create(
            {
                "name": "Test Workcenter",
            }
        )

        self.qcp_category = self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "equipment_category_ids": [(4, self.category.id)],
            }
        )

        self.qcp_workcenter = self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "workcenter_ids": [(4, self.workcenter.id)],
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
