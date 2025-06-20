import json
import logging
import time
from datetime import datetime
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import requests
from pydantic import BaseModel
from werkzeug.urls import url_join

from .schema import (
    Address,
    Box,
    Cuboid,
    Date,
    Destination,
    LengthUnitEnum,
    Origin,
    Package,
    PackagePackagingProperties,
    PackageTypeEnum,
    PhoneNumber,
    PickupDetails,
    Rate,
    RateRequestData,
    RateResponse,
    RateStatus,
    Shipment,
    ShipmentRequest,
    ShippingDetails,
    TimeOfDay,
    Weight,
    WeightUnitEnum,
)

_logger = logging.getLogger(__name__)


class ClickshipProvider:
    def __init__(self, debug_logger, prod_environment: bool = False, token=None):
        self.debug_logger = debug_logger
        self.session = requests.Session()
        self.token = token

        if not prod_environment:
            self.url = "https://customer-external-api.ssd-test.freightcom.com"
        else:
            self.url = "https://external-api.freightcom.com/"

    def _make_api_request(self, endpoint, method="GET", payload=None):
        if payload is None:
            payload = {}
        headers = {"Content-Type": "application/json", "Authorization": f"{self.token}"}
        access_url = url_join(self.url, endpoint)

        if isinstance(payload, BaseModel):
            payload = payload.model_dump_json(exclude_none=True)

        try:
            self.debug_logger(
                f"{access_url} {method} \n {payload}",
                f"clickship_request_{endpoint}",
            )

            response = self.session.request(
                method, access_url, data=payload, headers=headers, timeout=30
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

    def get_rate(self, order, contact) -> Rate:
        details = self._make_shipping_details(order, contact)
        data = RateRequestData(details=details)
        rate_id = self._post_request_rate(data)

        rate_response = RateResponse(status=RateStatus(done=False), rates=[])
        while not rate_response.status.done:
            time.sleep(1)
            rate_response = self._get_requested_rate(rate_id)

        rate = self._choose_carrier(rate_response.rates)
        return rate

    def _post_request_rate(self, data: RateRequestData) -> str:
        response = self._make_api_request("rate", "POST", payload=data)

        return response["request_id"]

    def _get_requested_rate(self, rate_id: str) -> RateResponse:
        response = self._make_api_request(f"rate/{rate_id}", "GET")
        response = RateResponse.model_validate(response)
        return response

    def book_shipment(self, picking, contact) -> None:
        rate = self.get_rate(picking, contact)
        data = self._make_shipment_request(picking, contact, rate.service_id)
        shipment_id = self._post_book_shipment(data)

        shipment: Shipment = self._get_shipment_status(shipment_id)
        price = int(shipment.rate.total.value) / 100
        labels = shipment.labels

        zpl_labels = [
            x
            for x in filter(
                lambda x: x["format"] == "zpl" and x["size"] == "a6", labels
            )
        ]

        label_data = self._fetch_label_data(zpl_labels[0]["url"])  # noqa: F841

        res = {
            "exact_price": price,
            "tracking_number": shipment.primary_tracking_number,
            "label_data": label_data,
            "tracking_url": shipment.tracking_url,
        }
        _logger.warning(shipment)
        return res

    def _fetch_label_data(self, url: str) -> str:
        data = urlopen(url, timeout=30)
        return data.read().decode("UTF-8")

    def _choose_carrier(self, rates: list[Rate]) -> Rate:
        return rates[0]

    def _post_book_shipment(self, shipment_data: ShipmentRequest) -> str:
        # Books a shipment for shipment_data, getting a shipment_id back
        response = self._make_api_request("shipment", "POST", payload=shipment_data)
        return response["id"]

    def _get_shipment_status(self, shipment_id: str) -> dict:
        # Fetches the shipment status for a known shipment ID
        response = self._make_api_request(f"shipment/{shipment_id}", "GET")
        response = Shipment.model_validate(response["shipment"])
        return response

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

    def _get_origin(self, order, contact) -> Origin:
        company = order.company_id
        origin = Origin(
            name=company.name,
            address=self._make_address(company),
            phone_number=PhoneNumber(number=company.phone),
            email_addresses=[company.email],
            contact_name=contact.name,
        )
        return origin

    def _make_current_date(self) -> Date:
        current_date = datetime.now(ZoneInfo("America/Montreal"))
        return Date(
            year=current_date.year, month=current_date.month, day=current_date.day
        )

    def _make_destination(self, order) -> Destination:
        client = order.partner_id
        destination = Destination(
            name=client.name,
            address=self._make_address(client),
            residential=True,
            phone_number=None if not client.phone else PhoneNumber(number=client.phone),
            email_addresses=None if not client.email else [client.email],
            contact_name=client.name,
        )
        return destination

    def _make_address(self, partner) -> Address:
        address = Address(
            address_line_1=partner.street,
            address_line_2=partner.street2 or None,
            city=partner.city,
            region=partner.state_id.code,
            country=partner.country_id.code,
            postal_code=partner.zip,
        )
        return address

    def _make_shipping_details(self, order, contact) -> ShippingDetails:
        origin = self._get_origin(order, contact)
        destination = self._make_destination(order)

        current_date = self._make_current_date()

        details = ShippingDetails(
            origin=origin,
            destination=destination,
            expected_ship_date=current_date,
            packaging_type=PackageTypeEnum.package.value,
            packaging_properties=PackagePackagingProperties(
                packages=[
                    Package(
                        description="Cube carboard box",
                        measurements=Box(
                            weight=Weight(unit=WeightUnitEnum.lb.value, value=10),
                            cuboid=Cuboid(
                                unit=LengthUnitEnum.inch.value, l=10, w=10, h=10
                            ),
                        ),
                    )
                ]
            ),
        )
        return details

    def _make_pickup_details(self, contact) -> PickupDetails:
        details = PickupDetails(
            date=self._make_current_date(),
            ready_at=TimeOfDay(hour=8, minute=0),
            ready_until=TimeOfDay(hour=16, minute=0),
            pickup_location="Docks",
            contact_name=contact.name,
            contact_phone_number=PhoneNumber(number=contact.work_phone),
        )

        return details

    def _make_shipment_request(self, order, contact, service_id) -> ShipmentRequest:
        unique_id = getattr(order, "origin", False) or order.name
        payment_method = (
            "zgvd7e7laioTa43K7xs6zHblpwKukQCy"  # TODO: Inject semi-dynamic method
        )
        shipping_details = self._make_shipping_details(order, contact)
        pickup_details = self._make_pickup_details(contact)

        request = ShipmentRequest(
            unique_id=unique_id,
            payment_method_id=payment_method,
            service_id=service_id,
            details=shipping_details,
            pickup_details=pickup_details,
        )
        return request

    def _get_payment_methods(self) -> list:
        return self._make_api_request("finance/payment-methods", "GET")[0]
