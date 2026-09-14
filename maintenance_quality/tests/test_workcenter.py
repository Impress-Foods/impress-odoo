import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestWorkCenter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workcenter_model = cls.env["mrp.workcenter"]
        cls.qcp_model = cls.env["quality.point"]

        cls.workcenter = cls.workcenter_model.create(
            {
                "name": "Test Workcenter",
            }
        )

        cls.qcp = cls.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "workcenter_ids": [(4, cls.workcenter.id)],
            }
        )

    def test_compute_quality_point_count_workcenter(self):
        self.assertEqual(self.workcenter.quality_point_count, 1)
