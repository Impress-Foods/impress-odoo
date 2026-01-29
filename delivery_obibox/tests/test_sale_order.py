import json
import logging
from unittest.mock import patch

from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


class TestSaleOrder(TestDeliveryCommon):
    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_get_rate_order(self, mock_api):
        mock_api.return_value = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )

        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        expected_response = {
            "success": True,
            "price": 8.66,
            "error_message": False,
            "warning_message": False,
        }
        response = self.sr.get_rate(so)
        self.assertEqual(expected_response, response)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_full_get_rate_so(self, mock_api):
        mock_api.return_value = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )

        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        wizard_action = so.action_open_delivery_wizard()
        wizard = (
            self.env["choose.delivery.carrier"]
            .with_context(**wizard_action["context"])
            .create({"carrier_id": self.obibox_method.id})
        )
        wizard.update_price()
        wizard.button_confirm()

        self.assertEqual(len(so.order_line), 1)
        self.assertEqual(so.order_line[0].product_id, self.obibox_method.product_id)
        self.assertEqual(so.order_line[0].price_subtotal, 8.66)
