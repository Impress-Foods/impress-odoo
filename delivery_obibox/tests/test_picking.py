import base64
import json
import logging
from datetime import datetime, timezone
from unittest.mock import patch

from freezegun import freeze_time

from odoo import tools
from odoo.exceptions import ValidationError

from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


def rate_response():
    return json.loads(
        """[{"ServiceName": "NEXTDAY",
        "PickupETA": "2025-07-09T11:00:00-04:00",
        "DeliveryETA": "2025-07-10T07:00:00-04:00",
        "PriceInCAD": 8.66
    }
    ]"""
    )


def tracking_response(tracking_numbers):
    return [
        {
            "Hub": "QUE",
            "RouteCode": "T-202",
            "TrackingNumber": tracking_number,
        }
        for tracking_number in tracking_numbers
    ]


def zpl_response(label="^XA^FDLabel^FS^XZ"):
    return {"Waybill": label}


def pdf_response():
    pdf = tools.file_open("base/tests/minimal.pdf", "rb").read()
    return {"Waybill": base64.b64encode(pdf).decode()}


class TestPicking(TestDeliveryCommon):
    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15, tzinfo=timezone.utc))
    def test_complete_book_shipment_1_package(self, mock_api):
        mock_api.side_effect = [
            rate_response(),
            tracking_response(["trackingNo"]),
            zpl_response(),
            pdf_response(),
        ]

        picking = self.make_picking()

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo", picking.obibox_tracking_numbers)
        self.assertTrue(picking.shipping_label_zpl_id)
        self.assertTrue(picking.shipping_label_pdf_id)
        self.assertEqual("text/plain", picking.shipping_label_zpl_id.mimetype)
        self.assertEqual("application/pdf", picking.shipping_label_pdf_id.mimetype)
        self.assertEqual(
            picking.shipping_label_zpl_id,
            picking.shipping_label_attachment_id,
        )

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15, tzinfo=timezone.utc))
    def test_complete_book_shipment_2_package(self, mock_api):
        mock_api.side_effect = [
            rate_response(),
            tracking_response(["trackingNo", "trackingNo2"]),
            zpl_response("^XA^FDLabel1^FS^XZ"),
            zpl_response("^XA^FDLabel2^FS^XZ"),
            pdf_response(),
            pdf_response(),
        ]

        picking = self.make_picking(n_packages=2)

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo,trackingNo2", picking.obibox_tracking_numbers)
        self.assertTrue(picking.shipping_label_zpl_id)
        self.assertTrue(picking.shipping_label_pdf_id)
        self.assertTrue(picking.shipping_label_attachment_id)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15, tzinfo=timezone.utc))
    def test_complete_book_shipment_pdf_format(self, mock_api):
        self.obibox_method.obibox_label_format = "pdf"
        mock_api.side_effect = [
            rate_response(),
            tracking_response(["trackingNo"]),
            zpl_response(),
            pdf_response(),
        ]

        picking = self.make_picking()

        picking.button_validate()
        self.assertEqual(
            picking.shipping_label_pdf_id,
            picking.shipping_label_attachment_id,
        )

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._get_label_data",
        side_effect=ValidationError("Label service unavailable"),
    )
    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15, tzinfo=timezone.utc))
    def test_label_failure_keeps_tracking(self, mock_api, _mock_label_data):
        mock_api.side_effect = [
            rate_response(),
            tracking_response(["trackingNo"]),
        ]

        picking = self.make_picking()

        picking.button_validate()
        self.assertEqual("trackingNo", picking.obibox_tracking_numbers)
        self.assertFalse(picking.shipping_label_zpl_id)
        self.assertFalse(picking.shipping_label_pdf_id)
        self.assertFalse(picking.shipping_label_attachment_id)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15, tzinfo=timezone.utc))
    def test_cancel_shipment(self, mock_api):
        mock_api.side_effect = [
            rate_response(),
            tracking_response(["trackingNo", "trackingNo2"]),
            zpl_response(),
            zpl_response(),
            pdf_response(),
            pdf_response(),
            True,
            True,
        ]

        picking = self.make_picking()
        picking.button_validate()
        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref)
        self.assertFalse(picking.shipping_label_zpl_id)
        self.assertFalse(picking.shipping_label_pdf_id)
        self.assertFalse(picking.shipping_label_attachment_id)
        self.assertFalse(picking.obibox_tracking_numbers)
