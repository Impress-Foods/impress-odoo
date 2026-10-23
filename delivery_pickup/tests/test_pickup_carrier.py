import base64
from unittest.mock import patch

from odoo.addons.delivery_common.tests.test_delivery_common import TestDeliveryCommon


class TestPickupCarrier(TestDeliveryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        delivery_product = cls.env["product.product"].create(
            {
                "name": "Pickup Delivery Product",
                "type": "service",
            }
        )
        cls.pickup_carrier = cls.env["delivery.carrier"].create(
            {
                "name": "Pickup",
                "delivery_type": "pickup",
                "integration_level": "rate_and_ship",
                "product_id": delivery_product.id,
            }
        )
        cls.out.print_label = True

    def make_pickup_picking(self, n_packages=1):
        picking = self.make_picking(n_packages=n_packages)
        picking.carrier_id = self.pickup_carrier
        return picking

    def test_send_shipping_creates_zpl_and_pdf_labels(self):
        picking = self.make_pickup_picking(n_packages=2)
        report_model = type(self.env["ir.actions.report"])
        original_render = report_model._render

        def render(report, report_ref, res_ids, data=None):
            if report_ref == "delivery_pickup.pickup_delivery_label_pdf":
                return b"%PDF-1.4\n%%EOF", "pdf"
            return original_render(report, report_ref, res_ids, data=data)

        with patch.object(report_model, "_render", render):
            picking.button_validate()

        self.assertTrue(picking.shipping_label_zpl_id)
        self.assertTrue(picking.shipping_label_pdf_id)
        self.assertEqual(
            picking.shipping_label_attachment_id,
            picking.shipping_label_zpl_id,
        )
        self.assertEqual("text/plain", picking.shipping_label_zpl_id.mimetype)
        self.assertEqual("application/pdf", picking.shipping_label_pdf_id.mimetype)

        zpl = base64.b64decode(picking.shipping_label_zpl_id.datas).decode()
        self.assertEqual(2, zpl.count("^XA"))
        self.assertIn("Pick Up", zpl)

        pdf = base64.b64decode(picking.shipping_label_pdf_id.datas)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_pdf_report_contains_one_label_per_package(self):
        picking = self.make_pickup_picking(n_packages=2)
        picking.button_validate()

        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                "delivery_pickup.pickup_delivery_label_pdf", picking.ids
            )[0]
            .decode()
        )

        self.assertEqual(2, html.count("PICK UP"))
        self.assertIn("1/2", html)
        self.assertIn("2/2", html)
        self.assertEqual(1, html.count("page-break-after: always"))

    def test_pdf_report_body_keeps_utf8_charset(self):
        picking = self.make_pickup_picking()
        picking.button_validate()
        report = self.env["ir.actions.report"]

        html = report._render_qweb_html(
            "delivery_pickup.pickup_delivery_label_pdf", picking.ids
        )[0]
        bodies, _html_ids, _header, _footer, _args = report._prepare_html(
            html, report_model="stock.picking"
        )

        self.assertIn('<meta charset="utf-8"/>', bodies[0])
        self.assertIn("Québec", bodies[0])
        self.assertNotIn("QuÃ©bec", bodies[0])

    def test_send_shipping_replaces_previous_labels(self):
        picking = self.make_pickup_picking()
        picking.button_validate()
        previous_attachments = (
            picking.shipping_label_zpl_id | picking.shipping_label_pdf_id
        )

        self.pickup_carrier.pickup_send_shipping(picking)

        self.assertFalse(previous_attachments.exists())
        self.assertTrue(picking.shipping_label_zpl_id)
        self.assertTrue(picking.shipping_label_pdf_id)
        self.assertEqual(
            picking.shipping_label_attachment_id,
            picking.shipping_label_zpl_id,
        )

    def test_cancel_shipment_removes_both_labels(self):
        picking = self.make_pickup_picking()
        picking.button_validate()
        attachments = picking.shipping_label_zpl_id | picking.shipping_label_pdf_id

        self.pickup_carrier.pickup_cancel_shipment(picking)

        self.assertFalse(attachments.exists())
        self.assertFalse(picking.shipping_label_attachment_id)
        self.assertFalse(picking.shipping_label_zpl_id)
        self.assertFalse(picking.shipping_label_pdf_id)
