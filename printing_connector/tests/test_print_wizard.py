from odoo.exceptions import ValidationError

from .test_common import TestCommon


class TestPrintWizard(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.printer_model = cls.env["print.printer"]
        cls.server = cls.env["print.server"].create(
            {"name": "server", "method": "get", "url": "http://localhost"}
        )
        cls.other_server = cls.env["print.server"].create(
            {"name": "other-server", "method": "get", "url": "http://localhost"}
        )
        cls.printer = cls.printer_model.create(
            {
                "name": "printer",
                "technical_name": "PRINTER",
                "server_id": cls.server.id,
            }
        )
        cls.other_printer = cls.printer_model.create(
            {
                "name": "other-printer",
                "technical_name": "OTHER",
                "server_id": cls.other_server.id,
            }
        )

        cls.print_report = cls.make_single_field_report(
            "product.product", "name", "name"
        )[0]
        cls.print_report.print_server_id = cls.server
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "api report",
                "model": "product.product",
                "report_type": "api",
                "report_name": "printing_connector.test_api_label",
                "print_report_id": cls.print_report.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"type": "consu", "name": "wizard product"}
        )

    def _open_wizard(self, **kwargs):
        action = self.env["print.wizard"].open_wizard(
            self.report.id, [self.product.id], **kwargs
        )
        return self.env["print.wizard"].browse(action["res_id"]), action

    def test_open_wizard_returns_action(self):
        wizard, action = self._open_wizard()
        self.assertEqual(action["res_model"], "print.wizard")
        self.assertTrue(wizard.exists())
        self.assertEqual(wizard.ir_actions_report_id, self.report)
        self.assertEqual(wizard.qty, 1)

    def test_open_wizard_rejects_non_api_report(self):
        report = self.report.copy({"report_type": "qweb-pdf"})
        with self.assertRaises(ValidationError):
            self.env["print.wizard"].open_wizard(report.id, [self.product.id])

    def test_open_wizard_applies_defaults(self):
        wizard, _ = self._open_wizard(
            defaults={"printer_id": self.printer.id, "qty": 3}
        )
        self.assertEqual(wizard.printer_id, self.printer)
        self.assertEqual(wizard.qty, 3)

    def test_open_wizard_builds_preview_lines(self):
        wizard, _ = self._open_wizard(defaults={"preview": {"name": "widget"}})
        self.assertEqual(len(wizard.preview_ids), 1)
        self.assertEqual(wizard.preview_ids.key, "name")
        self.assertEqual(wizard.preview_ids.value, "widget")

    def test_available_printer_ids_filtered_by_server(self):
        wizard, _ = self._open_wizard()
        self.assertIn(self.printer, wizard.available_printer_ids)
        self.assertNotIn(self.other_printer, wizard.available_printer_ids)

    def test_action_confirm_stores_selection(self):
        wizard, _ = self._open_wizard(defaults={"printer_id": self.printer.id})
        wizard.qty = 4

        result = wizard.action_confirm()

        self.assertEqual(result, {"type": "ir.actions.act_window_close"})
        self.assertTrue(wizard.result_ready)
        self.assertEqual(wizard.result_printer_id, self.printer)
        self.assertEqual(wizard.result_printer_name, "PRINTER")
        self.assertEqual(wizard.result_qty, 4)
