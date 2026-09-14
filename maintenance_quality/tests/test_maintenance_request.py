import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestMaintenanceRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        equipment_model = cls.env["maintenance.equipment"]
        qcp_model = cls.env["quality.point"]

        cls.category = cls.env["maintenance.equipment.category"].create(
            {
                "name": "Test Category",
            }
        )

        cls.workcenter = cls.env["mrp.workcenter"].create(
            {
                "name": "Test Workcenter",
            }
        )

        cls.equipment = equipment_model.create(
            {
                "name": "Test Equipment",
            }
        )

        cls.equipment_cat = equipment_model.create(
            {
                "name": "Test Equipment",
                "category_id": cls.category.id,
            }
        )

        cls.equipment_wc = equipment_model.create(
            {
                "name": "Test Equipment",
                "workcenter_id": cls.workcenter.id,
            }
        )

        cls.equipment_cat_wc = equipment_model.create(
            {
                "name": "Test Equipment",
                "category_id": cls.category.id,
                "workcenter_id": cls.workcenter.id,
            }
        )

        cls.qcp_equipment = qcp_model.create(
            {
                "name": "Test QCP",
                "check_corrective": True,
                "equipment_ids": [(4, cls.equipment.id)],
                "control_point_type": "maintenance",
            }
        )

        cls.qcp_cat = qcp_model.create(
            {
                "name": "Test QCP",
                "check_corrective": True,
                "equipment_category_ids": [(4, cls.category.id)],
                "control_point_type": "maintenance",
            }
        )

        cls.qcp_wc = qcp_model.create(
            {
                "name": "Test QCP",
                "check_corrective": True,
                "workcenter_ids": [(4, cls.workcenter.id)],
                "control_point_type": "maintenance",
            }
        )

        cls.qcp_preventive = qcp_model.create(
            {
                "name": "Test QCP",
                "check_preventive": True,
                "equipment_ids": [(4, cls.equipment.id)],
                "equipment_category_ids": [(4, cls.category.id)],
                "workcenter_ids": [(4, cls.workcenter.id)],
                "control_point_type": "maintenance",
            }
        )

    # Simple quality check creation tests
    def test_create_quality_check_on_maintenance_equipment_equipment(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "equipment_id": self.equipment.id,
            }
        )

        self.assertEqual(len(request.quality_check_ids), 1)

    def test_create_quality_check_on_maintenance_equipment_equipment_category(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "equipment_id": self.equipment_cat.id,
            }
        )

        self.assertEqual(len(request.quality_check_ids), 1)

    def test_create_quality_check_on_maintenance_equipment_workcenter(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "equipment_id": self.equipment_wc.id,
            }
        )

        self.assertEqual(len(request.quality_check_ids), 1)

    def test_create_quality_check_on_maintenance_workcenter(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
            }
        )

        self.assertEqual(len(request.quality_check_ids), 1)

    def test_create_quality_check_on_maintenance_category_workcenter(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "equipment_id": self.equipment_cat_wc.id,
            }
        )

        self.assertEqual(len(request.quality_check_ids), 2)

    def test_create_quality_check_on_maintenance_preventive(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
                "maintenance_type": "preventive",
            }
        )

        self.assertEqual(len(request.quality_check_ids), 1)

    def test_quality_check_to_do_count(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
            }
        )
        self.assertEqual(request.quality_check_todo_count, 1)

    def test_quality_check_fail_count(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
            }
        )
        request.quality_check_ids[0].do_fail()
        self.assertEqual(request.quality_check_fail_count, 1)

    def test_quality_check_pass_count(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
            }
        )
        request.quality_check_ids[0].do_pass()
        self.assertEqual(request.quality_check_pass_count, 1)

    def test_quality_check_fail_create_alert(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Test Request",
                "workcenter_id": self.workcenter.id,
            }
        )

        check = request.quality_check_ids[0]
        check.do_fail()
        check.do_alert()

        self.assertEqual(request, check.alert_ids[0].maintenance_request_id)
