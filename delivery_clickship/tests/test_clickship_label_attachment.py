import base64
from unittest.mock import patch

from .test_delivery_common import TestDeliveryCommon


class TestClickshipLabelAttachment(TestDeliveryCommon):
    def _book_with_labels(self, label_data):
        return {
            "tracking_url": "https://example.test/track",
            "shipment_id": "shipment-1",
            "label_data": label_data,
        }

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.book_shipment"
    )
    def test_send_shipping_stores_base64_labels_as_is(self, mock_book):
        """Labels arrive base64-encoded from the API and must not be re-encoded.

        Regression: when delivery_pickup is also installed, its override of the
        same helper name used to base64-encode this already-encoded str.
        """
        pdf_b64 = base64.b64encode(b"%PDF-1.4 clickship").decode()
        zpl_b64 = base64.b64encode(b"^XA^XZ").decode()
        mock_book.return_value = self._book_with_labels(
            {"pdf": pdf_b64, "zpl": zpl_b64}
        )
        picking = self.make_picking()

        self.clickship_method.clickship_send_shipping(picking)

        pdf = base64.b64decode(picking.shipping_label_pdf_id.datas)
        zpl = base64.b64decode(picking.shipping_label_zpl_id.datas)
        self.assertEqual(b"%PDF-1.4 clickship", pdf)
        self.assertEqual(b"^XA^XZ", zpl)
        self.assertEqual(
            picking.shipping_label_zpl_id,
            picking.shipping_label_attachment_id,
        )

    @patch(
        "odoo.addons.delivery_clickship.models.clickship_request.ClickshipProvider.book_shipment"
    )
    def test_send_shipping_without_labels_creates_no_attachments(self, mock_book):
        """An empty label_data must not raise and must not create attachments."""
        mock_book.return_value = self._book_with_labels({})
        picking = self.make_picking()

        self.clickship_method.clickship_send_shipping(picking)

        self.assertFalse(picking.shipping_label_pdf_id)
        self.assertFalse(picking.shipping_label_zpl_id)
        self.assertFalse(picking.shipping_label_attachment_id)
