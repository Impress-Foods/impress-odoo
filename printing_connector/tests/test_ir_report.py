from .test_common import TestCommon


class TestIrReport(TestCommon):
    def test_render_api(self):
        report, _ = self.make_single_field_report("product.product", "name", "name")

        product = self.env["product.product"].create(
            {"type": "consu", "name": "product"}
        )

        ir_report = self.env["ir.actions.report"].create(
            {
                "name": "test",
                "print_report_id": report.id,
                "report_type": "api",
                "report_name": "report",
                "report_file": "report",
                "model": "product.product",
            }
        )

        value = ir_report._render(ir_report, product.id, data=None)

        self.assertDictEqual(value, {"_template": "test", "name": "product"})

    def test_render_api_empty_recordset(self):
        report, _ = self.make_single_field_report("product.product", "name", "name")

        ir_report = self.env["ir.actions.report"].create(
            {
                "name": "test",
                "print_report_id": report.id,
                "report_type": "api",
                "report_name": "report",
                "report_file": "report",
                "model": "product.product",
            }
        )

        with self.assertRaises(ValueError):
            ir_report._render(ir_report, (), data=None)

    def test_render_api_multiple_records(self):
        report, _ = self.make_single_field_report("product.product", "name", "name")

        ir_report = self.env["ir.actions.report"].create(
            {
                "name": "test",
                "print_report_id": report.id,
                "report_type": "api",
                "report_name": "report",
                "report_file": "report",
                "model": "product.product",
            }
        )

        with self.assertRaises(ValueError):
            ir_report._render(ir_report, (1, 2), data=None)
