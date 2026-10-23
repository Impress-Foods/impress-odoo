import base64
import io

from odoo import tools
from odoo.exceptions import UserError

from .test_delivery_common import TestDeliveryCommon


class TestShippingLabel(TestDeliveryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdf = tools.file_open("base/tests/minimal.pdf", "rb").read()
        cls.zpl = b"^XA^FDLabel^FS^XZ"

    def _set_label(self, picking, content, name, mimetype):
        attachment = self.env["ir.attachment"].create(
            {
                "name": name,
                "type": "binary",
                "datas": base64.b64encode(content).decode(),
                "res_model": "stock.picking",
                "res_id": picking.id,
                "mimetype": mimetype,
            }
        )
        picking.shipping_label_attachment_id = attachment
        return attachment

    def test_get_report_values_ignores_pdf(self):
        zpl_picking = self.make_picking()
        pdf_picking = self.make_picking()
        self._set_label(zpl_picking, self.zpl, "label.zpl", "text/plain")
        self._set_label(pdf_picking, self.pdf, "label.pdf", "application/pdf")

        report = self.env["report.delivery_common.report_shipping_label_view"]
        values = report._get_report_values((zpl_picking | pdf_picking).ids, {})

        self.assertEqual([self.zpl.decode()], values["docs"])

    def test_render_pdf_report(self):
        picking = self.make_picking()
        self._set_label(picking, self.pdf, "label.pdf", "application/pdf")

        report = self.env["ir.actions.report"]
        content, report_type = report._render_qweb_pdf(
            "delivery_common.report_shipping_label_pdf",
            picking.ids,
        )

        self.assertEqual("pdf", report_type)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_render_pdf_report_multiple_pickings(self):
        first = self.make_picking()
        second = self.make_picking()
        self._set_label(first, self.pdf, "label-1.pdf", "application/pdf")
        self._set_label(second, self.pdf, "label-2.pdf", "application/pdf")

        report = self.env["ir.actions.report"]
        content, report_type = report._render_qweb_pdf(
            "delivery_common.report_shipping_label_pdf",
            (first | second).ids,
        )

        self.assertEqual("pdf", report_type)
        reader = tools.pdf.OdooPdfFileReader(io.BytesIO(content))
        self.assertEqual(2, reader.getNumPages())

    def test_render_pdf_report_without_pdf(self):
        picking = self.make_picking()
        self._set_label(picking, self.zpl, "label.zpl", "text/plain")

        report = self.env["ir.actions.report"]
        with self.assertRaises(UserError):
            report._render_qweb_pdf(
                "delivery_common.report_shipping_label_pdf",
                picking.ids,
            )

    def test_print_action_uses_zpl_report(self):
        picking = self.make_picking()
        self._set_label(picking, self.zpl, "label.zpl", "text/plain")

        action = picking.action_print_shipping_label()

        self.assertEqual(
            self.env.ref("delivery_common.report_shipping_label").report_name,
            action["report_name"],
        )

    def test_print_action_uses_pdf_report(self):
        picking = self.make_picking()
        self._set_label(picking, self.pdf, "label.pdf", "application/pdf")

        action = picking.action_print_shipping_label()

        self.assertEqual(
            self.env.ref("delivery_common.report_shipping_label_pdf").report_name,
            action["report_name"],
        )

    def test_autoprint_routes_each_format(self):
        self.out.auto_print_delivery_label = True
        zpl_picking = self.make_picking()
        pdf_picking = self.make_picking()
        self._set_label(zpl_picking, self.zpl, "label.zpl", "text/plain")
        self._set_label(pdf_picking, self.pdf, "label.pdf", "application/pdf")

        actions = (zpl_picking | pdf_picking)._get_autoprint_report_actions()

        report_names = {action["report_name"] for action in actions}
        self.assertIn(
            self.env.ref("delivery_common.report_shipping_label").report_name,
            report_names,
        )
        self.assertIn(
            self.env.ref("delivery_common.report_shipping_label_pdf").report_name,
            report_names,
        )

    def test_delete_labels(self):
        picking = self.make_picking()
        zpl = self._set_label(picking, self.zpl, "label.zpl", "text/plain")
        pdf = self._set_label(picking, self.pdf, "label.pdf", "application/pdf")
        picking.write(
            {
                "shipping_label_attachment_id": zpl.id,
                "shipping_label_zpl_id": zpl.id,
                "shipping_label_pdf_id": pdf.id,
            }
        )

        picking.delete_labels()

        self.assertFalse(picking.shipping_label_attachment_id)
        self.assertFalse(picking.shipping_label_zpl_id)
        self.assertFalse(picking.shipping_label_pdf_id)
        self.assertFalse((zpl | pdf).exists())
