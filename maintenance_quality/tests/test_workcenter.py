import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestWorkCenter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.workcenter_model = self.env["mrp.workcenter"]
        self.qcp_model = self.env["quality.point"]

        self.workcenter = self.workcenter_model.create(
            {
                "name": "Test Workcenter",
            }
        )

        self.qcp = self.qcp_model.create(
            {
                "name": "Test QCP",
                "control_point_type": "maintenance",
                "workcenter_ids": [(4, self.workcenter.id)],
            }
        )

    def test_compute_quality_point_count_workcenter(self):
        self.assertEqual(self.workcenter.quality_point_count, 1)
