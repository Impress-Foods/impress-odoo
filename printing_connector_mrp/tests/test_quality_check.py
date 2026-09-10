from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase


class TestQualityCheckApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "MRP Label Test", "type": "consu"}
        )
        cls.server = cls.env["print.server"].create(
            {"name": "test-server", "method": "get", "url": "http://localhost"}
        )
        cls.printer = cls.env["print.printer"].create(
            {
                "name": "Test Printer",
                "technical_name": "TEST-PRINTER",
                "server_id": cls.server.id,
            }
        )
        cls.second_printer = cls.env["print.printer"].create(
            {
                "name": "Second Printer",
                "technical_name": "SECOND-PRINTER",
                "server_id": cls.server.id,
            }
        )
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "WC-TEST"})

        cls.product_print_report = cls.env["print.report"].create(
            {
                "name": "product-label",
                "template": "test",
                "target_model_id": cls.env["ir.model"]
                .search([("model", "=", "product.product")], limit=1)
                .id,
            }
        )
        cls.lot_print_report = cls.env["print.report"].create(
            {
                "name": "lot-label",
                "template": "test",
                "target_model_id": cls.env["ir.model"]
                .search([("model", "=", "stock.lot")], limit=1)
                .id,
            }
        )
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "API Label (qc test)",
                "model": "quality.check",
                "report_type": "api",
                "report_name": "printing_connector_mrp.test_api_label",
                "print_report_id": cls.product_print_report.id,
            }
        )
        cls.point = cls.env["quality.point"].create(
            {
                "product_ids": [Command.set([cls.product.id])],
                "test_type_id": cls.env.ref("mrp_workorder.test_type_print_label").id,
                "test_report_type": "api",
                "report_id": cls.report.id,
                "printer_id": cls.printer.id,
            }
        )
        cls.check = cls.env["quality.check"].create(
            {
                "product_id": cls.product.id,
                "point_id": cls.point.id,
                "company_id": cls.env.company.id,
            }
        )

    def _point_with_target(self, model):
        print_report = self.env["print.report"].create(
            {
                "name": "tmp",
                "template": "test",
                "target_model_id": self.env["ir.model"]
                .search([("model", "=", model)], limit=1)
                .id,
            }
        )
        report = self.env["ir.actions.report"].create(
            {
                "name": "tmp",
                "model": "quality.check",
                "report_type": "api",
                "report_name": "printing_connector_mrp.test_api_label",
                "print_report_id": print_report.id,
            }
        )
        return self.env["quality.point"].create(
            {
                "product_ids": [Command.set([self.product.id])],
                "test_type_id": self.env.ref("mrp_workorder.test_type_print_label").id,
                "test_report_type": "api",
                "report_id": report.id,
                "printer_id": self.printer.id,
            }
        )

    def test_send_api_label_wrong_report_type_raises(self):
        bad_report = self.report.copy({"report_type": "qweb-pdf"})
        check = self.check.copy(
            {
                "point_id": self.env["quality.point"]
                .create(
                    {
                        "product_ids": [Command.set([self.product.id])],
                        "test_type_id": self.env.ref(
                            "mrp_workorder.test_type_print_label"
                        ).id,
                        "test_report_type": "pdf",
                        "report_id": bad_report.id,
                        "printer_id": self.printer.id,
                    }
                )
                .id
            }
        )
        with self.assertRaises(ValidationError):
            check._send_api_label()

    def test_get_record_product_ok(self):
        self.assertEqual(self.check._get_record_for_api_report(), self.check.product_id)

    def test_get_record_product_missing_raises(self):
        check = self.env["quality.check"].new(
            {"point_id": self.point.id, "company_id": self.env.company.id}
        )
        with self.assertRaises(ValidationError):
            check._get_record_for_api_report()

    def test_get_record_unsupported_model_raises(self):
        point = self._point_with_target("res.partner")
        check = self.env["quality.check"].new(
            {
                "point_id": point.id,
                "product_id": self.product.id,
                "company_id": self.env.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            check._get_record_for_api_report()

    def test_get_record_lot_empty_raises(self):
        point = self._point_with_target("stock.lot")
        check = self.env["quality.check"].new(
            {
                "point_id": point.id,
                "product_id": self.product.id,
                "company_id": self.env.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            check._get_record_for_api_report()

    def test_get_printer_priority(self):
        # point printer wins by default
        self.assertEqual(self.check._get_printer(), self.point.printer_id)
        # workcenter default when point has none
        self.point.printer_id = False
        self.workcenter.default_printer_id = self.second_printer
        self.check.workcenter_id = self.workcenter
        self.assertEqual(self.check._get_printer(), self.second_printer)
        # context override wins over everything
        check = self.check.with_context(printing_printer_override=self.printer.id)
        self.assertEqual(check._get_printer(), self.printer)

    def test_get_printer_none_raises(self):
        self.point.printer_id = False
        self.workcenter.default_printer_id = False
        self.check.workcenter_id = self.workcenter
        with self.assertRaises(ValidationError):
            self.check._get_printer()

    def test_get_print_qty_context_override(self):
        check = self.check.with_context(printing_printing_quantity=7)
        self.assertEqual(check._get_print_qty(), 7)

    def test_get_print_qty_falls_back_to_super(self):
        self.assertTrue(isinstance(self.check._get_print_qty(), int))

    def test_get_print_job_name_fallback(self):
        check = self.env["quality.check"].new(
            {
                "point_id": self.point.id,
                "product_id": self.product.id,
                "company_id": self.env.company.id,
            }
        )
        self.assertEqual(check._get_print_job_name(), check.display_name)

    def test_get_print_job_name_workorder(self):
        workorder = self.env["mrp.workorder"].new({"name": "WO-TEST"})
        check = self.env["quality.check"].new(
            {
                "point_id": self.point.id,
                "product_id": self.product.id,
                "company_id": self.env.company.id,
                "workorder_id": workorder.id,
            }
        )
        self.assertEqual(check._get_print_job_name(), check.workorder_id.display_name)

    def test_label_action_dispatch_api(self):
        sentinel = {"sentinel": True}
        with (
            patch.object(
                type(self.check),
                "_send_api_label",
                return_value=sentinel,
            ),
        ):
            self.assertEqual(self.check._get_product_label_action("api"), sentinel)
            self.assertEqual(self.check._get_lot_label_action("api"), sentinel)

    def test_get_print_data(self):
        data = self.check.get_print_data()
        self.assertIn("printers", data)
        self.assertTrue(any(p["name"] == "Test Printer" for p in data["printers"]))
        self.assertEqual(data["_printer_id"], self.printer.id)
        self.assertTrue(isinstance(data["_qty"], int))
        self.assertTrue(isinstance(data["data"], dict))
