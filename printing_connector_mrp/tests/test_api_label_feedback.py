import logging

from odoo.fields import Command
from odoo.tests import TransactionCase

_logger = logging.getLogger(__name__)


class TestApiLabelFeedbackContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({"name": "PrintFeedbackTest"})
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "API Label (feedback test)",
                "model": "quality.check",
                "report_type": "api",
                "report_name": "printing_connector_mrp.test_api_label",
            }
        )
        cls.point = cls.env["quality.point"].create(
            {
                "product_ids": [Command.set([cls.product.id])],
                "test_type_id": cls.env.ref("mrp_workorder.test_type_print_label").id,
                "test_report_type": "api",
                "report_id": cls.report.id,
            }
        )
        cls.check = cls.env["quality.check"].create(
            {
                "product_id": cls.product.id,
                "point_id": cls.point.id,
                "company_id": cls.env.company.id,
            }
        )

    def _send(self, from_shopfloor):
        QualityCheck = type(self.env["quality.check"])
        self.patch(QualityCheck, "_get_printer_name", lambda self: "dummy")
        self.patch(QualityCheck, "_get_print_qty", lambda self: 1)
        self.patch(
            QualityCheck, "_get_record_for_api_report", lambda self: self.product_id
        )
        ctx = {"discard_logo_check": True}
        if from_shopfloor:
            ctx["from_shopfloor"] = True
        return self.check.with_context(**ctx)._send_api_label()

    def test_from_shopfloor_propagates_to_action_context(self):
        action = self._send(from_shopfloor=True)
        self.assertTrue(
            action["context"].get("from_shopfloor"),
            "from_shopfloor must echo into the returned report action context",
        )

    def test_without_from_shopfloor_not_in_action_context(self):
        action = self._send(from_shopfloor=False)
        self.assertFalse(
            action["context"].get("from_shopfloor"),
            "from_shopfloor must be absent when not on the shop floor",
        )
