import json
import logging
from datetime import datetime
from unittest.mock import patch

from freezegun import freeze_time

from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


class TestPicking(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15))
    def test_complete_book_shipment_1_package(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }]"""
        )

        mock_api.side_effect = [return_value_1, return_value_2]

        picking = self.make_picking()

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo", picking.obibox_tracking_numbers)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15))
    def test_complete_book_shipment_2_package(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }, {
            "Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo2", "Waybill":"LabelData" }]"""
        )

        mock_api.side_effect = [return_value_1, return_value_2]

        picking = self.make_picking(n_packages=2)

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo,trackingNo2", picking.obibox_tracking_numbers)
        self.assertTrue(picking.shipping_label_attachment_id)  # type: ignore

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_cancel_shipment(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }, {
            "Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo2", "Waybill":"LabelData" }]"""
        )
        return_value_3 = True
        mock_api.side_effect = [
            return_value_1,
            return_value_2,
            return_value_3,
            return_value_3,  # twice since we have to cancel 2 packages
        ]

        picking = self.make_picking()
        picking.button_validate()
        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref)
        self.assertFalse(picking.shipping_label_attachment_id)  # type: ignore
