import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from werkzeug.urls import url_join

from .schema import (
    Address,
    Date,
    Destination,
    Origin,
    PhoneNumber,
    RateRequestData,
    RateStatus,
    Shipment,
    ShipmentDetails,
)

_logger = logging.getLogger(__name__)


class ClickshipProvider:
    def __init__(self, debug_logger, prod_environment: bool = False):
        self.debug_logger = debug_logger
        self.session = requests.Session()

        if not prod_environment:
            self.url = "TEST URL"
        else:
            self.url = "https://external-api.freightcom.com/"

    def _make_api_request(self, endpoint, method="GET", payload=None, token=None):
        headers = {"Content-Type": "application/json", "Authorization": token}

        access_url = url_join(self.url, endpoint)

        try:
            self.debug_logger(
                "%s\n%s" % (access_url, method, payload),  # noqa
                f"clickship_request_%s" & endpoint,  # noqa
            )  # noqa

            response = self.session.request(
                method, access_url, json=payload, headers=headers, timeout=30
            )
            response_json = response.json()

            self.debug_logger(
                f"{response.status_code}\n{response.text}",
                f"clickship_response_{endpoint}",
            )
            return response_json

        except requests.exceptions.ConnectionError as error:
            _logger.warning(
                f"Connection Error: {error} with the given URL: {access_url}"
            )
            return {
                "errors": {
                    "timeout": "Cannot reach the server. Please try again later."
                }
            }
        except json.decoder.JSONDecodeError as error:
            _logger.warning(f"JSONDecodeError: {error}")
            return {"errors": {"JSONDecodeError": str(error)}}

    def _post_request_rate(self, data: RateRequestData) -> str:
        # Requests a rate, getting a rate ID in return to poll back
        return ""

    def get_rate(self, order) -> dict:
        origin = self._get_origin(order)  # noqa
        destination = self._get_destination(order)  # noqa

        current_date = datetime.now(ZoneInfo("America/Montreal"))
        ship_date = Date(  # noqa
            year=current_date.year, month=current_date.month, day=current_date.day
        )

        details = ShipmentDetails()  # noqa

        data = RateRequestData()

        rate_id = self._post_request_rate(data)  # noqa

        return {}

    def _get_requested_rate(self, rate_id: str) -> RateStatus:
        # Fetches a known rate_id to get the rate data
        return {}

    def _post_book_shipment(self, shipment_data: Shipment) -> str:
        # Books a shipment for shipment_data, getting a shipment_id back
        return ""

    def _get_shipment_status(self, shipment_id: str) -> dict:
        # Fetches the shipment status for a known shipment ID
        return {}

    def _post_schedule_pickup(self, shipment_id: str, payload: dict) -> bool:
        # Requests a pickup for a known shipment_id. No return from API
        return True

    def _del_cancel_shipment(self, shipment_id: str) -> bool:
        # Deletes a known shipment_id. No return from API
        return True

    def _del_cancel_scheduling(self, shipment_id: str) -> bool:
        # Deletes a pickup/dispatch for a known shipment_id.
        # No return from API
        return True

    def _get_origin(self, order) -> Origin:
        company = order.company_id

        address = self._get_address(company)
        origin = Origin(
            name=company.name,
            address=address,
            phone_number=PhoneNumber(number=company.phone),
            email_addresses=[company.email],
        )
        return origin

    def _get_destination(self, order) -> Destination:
        client = order.partner_id
        destination = Destination(
            name=client.name,
            address=self._get_address(client),
            residential=True,
            phone_number=None if not client.phone else PhoneNumber(number=client.phone),
            email_addresses=None if not client.email else [client.email],
        )
        return destination

    def _get_address(self, partner) -> Address:
        address = (
            Address(
                address_line_1=partner.street,
                address_line_2=partner.street2 or None,
                city=partner.city,
                region=partner.state_id.name,
                country=partner.country_id.code,
                postal_code=partner.zip,
            ),
        )

        return address
