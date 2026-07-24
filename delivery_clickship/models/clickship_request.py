import json
import logging
import time
from datetime import datetime
from typing import Any
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import requests
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from werkzeug.urls import url_join

from odoo.exceptions import ValidationError
from odoo.orm.environments import Environment

from odoo.addons.base.models.res_company import ResCompany
from odoo.addons.base.models.res_partner import ResPartner
from odoo.addons.hr.models.hr_employee import HrEmployee
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.stock.models.stock_package import StockPackage
from odoo.addons.stock.models.stock_picking import StockPicking

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
    PickupRequest,
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
    def __init__(
        self,
        debug_logger,
        env: Environment,
        prod_environment: bool = False,
        token: str | None = None,
    ):
        self.debug_logger = debug_logger
        self.session = requests.Session()
        self.token = token
        self.env = env

        if not prod_environment:
            self.url = "https://customer-external-api.ssd-test.freightcom.com"
        else:
            self.url = "https://external-api.freightcom.com"

    def get_rate(self, order: StockPicking | SaleOrder, contact: HrEmployee) -> Rate:
        rate_response = self.get_raw_rates(order, contact)
        rates = rate_response.rates
        if len(rates) == 0:
            raise ValidationError(self.env._("Could not fetch any rates!"))

        if isinstance(order, StockPicking) and order.clickship_service_id:
            rate = [
                x
                for x in filter(
                    lambda x: x.service_id == order.clickship_service_id,
                    rates,
                )
            ].pop()
        else:
            rate = rates.pop()

        return rate

    def get_raw_rates(
        self, order: StockPicking | SaleOrder, contact: HrEmployee
    ) -> RateResponse:
        details = self._make_shipping_details(order, contact)
        data = RateRequestData(details=details)
        rate_id = self._post_request_rate(data)

        rate_response = RateResponse(status=RateStatus(done=False), rates=[])
        loops = 0

        while not rate_response.status.done and loops < 30:
            time.sleep(1)
            rate_response = self._get_requested_rate(rate_id)
            loops += 1

        if not rate_response.status.done:
            raise ValidationError(self.env._("Timed Out!"))

        return rate_response

    def book_shipment(
        self, picking: StockPicking, contact: HrEmployee
    ) -> dict[str, Any]:
        data = self._make_shipment_request(picking, contact)
        shipment_id = self._post_book_shipment(data)
        shipment: Shipment = self._get_shipment_status(shipment_id)

        price = int(shipment.rate.total.value) / 100
        labels = shipment.labels
        label_data = None
        if labels:
            zpl_labels = [
                x
                for x in filter(
                    lambda x: x["format"] == "zpl" and x["size"] == "a6", labels
                )
            ]

            label_data = self._fetch_label_data(zpl_labels[0]["url"])

        res = {
            "exact_price": price,
            "tracking_number": shipment.primary_tracking_number,
            "label_data": label_data,
            "tracking_url": shipment.tracking_url,
            "shipment_id": shipment_id,
        }
        return res

    def cancel_shipment(self, shipment_id: str) -> bool:
        self._del_cancel_shipment(shipment_id)
        return True

    def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: None | dict | BaseModel | str = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        if payload is None:
            payload = {}
        headers = {"Content-Type": "application/json", "Authorization": f"{self.token}"}
        access_url = url_join(self.url, endpoint)

        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)

        try:
            self.debug_logger(
                f"{access_url} {method} \n {payload}",
                f"clickship_request_{endpoint}",
            )
            match method:
                case "GET":
                    response = self.session.get(access_url, headers=headers, timeout=30)
                case "POST":
                    response = self.session.post(
                        access_url, json=payload, headers=headers, timeout=30
                    )
                case "DELETE":
                    response = self.session.delete(
                        access_url, data=payload, headers=headers, timeout=30
                    )
                case _:
                    self.debug_logger(
                        f"Unsupported method: {method}", f"clickship_request_{endpoint}"
                    )
                    return {
                        "errors": {
                            "method": "Unsupported method: %s" % method,
                        }
                    }

            response_json = response.json()

            self.debug_logger(
                f"{response.status_code}\n{response.text}",
                f"clickship_response_{endpoint}",
            )
            return response_json

        except requests.exceptions.ConnectionError as error:
            self.debug_logger(
                f"Connection Error: {error} with the given URL: {access_url}",
                "clickship_request",
            )
            return {
                "errors": {
                    "timeout": "Cannot reach the server. Please try again later."
                }
            }
        except json.decoder.JSONDecodeError as error:
            self.debug_logger(f"JSON Decode Issue: {error}", "clickship_request")
            return {"errors": {"JSONDecodeError": str(error)}}

    def _post_request_rate(self, data: RateRequestData) -> str:
        response = self._make_api_request("rate", "POST", payload=data)
        return response["request_id"]  # type: ignore

    def _get_requested_rate(self, rate_id: str) -> RateResponse:
        response = self._make_api_request(f"rate/{rate_id}", "GET")
        model = RateResponse.model_validate(response)
        return model

    def _post_book_shipment(self, shipment_data: ShipmentRequest) -> str:
        # Books a shipment for shipment_data, getting a shipment_id back
        try:
            response = self._make_api_request("shipment", "POST", payload=shipment_data)
            if not isinstance(response, dict):
                raise ValidationError(self.env._("response not a dict"))
            elif not isinstance(response["id"], str):
                raise ValidationError(self.env._("shipment_id not a string"))
            else:
                return response["id"]

        except KeyError:
            _logger.error(
                f"""Could not book shipment:\n {
                    shipment_data.model_dump_json(exclude_none=True)
                }"""
            )
            raise ValidationError(self.env._("Could not book shipment")) from KeyError

    def _get_shipment_status(self, shipment_id: str) -> Shipment:
        # Fetches the shipment status for a known shipment ID
        got_response = False
        response = self._make_api_request(f"shipment/{shipment_id}", "GET")
        loops = 0
        while not got_response and loops < 30:
            response = self._make_api_request(f"shipment/{shipment_id}", "GET")
            if isinstance(response, dict):
                got_response = not response.get("errors", False)
                time.sleep(1)
                loops += 1
            else:
                raise ValidationError(
                    self.env._(
                        "Could not get shipment status for %(id): %(response)",
                        id=shipment_id,
                        response=response,
                    )
                )

        if not got_response:
            raise ValidationError(self.env._("Timed out!"))
        try:
            if not isinstance(response, dict):
                raise ValidationError(self.env._("shipment not a dict"))
            return Shipment.model_validate(response["shipment"])

        except KeyError:
            raise ValidationError(
                self.env._(
                    "Could not get shipment status for %(id): %(response)",
                    id=shipment_id,
                    response=response,
                )
            ) from KeyError

    def _post_schedule_pickup(self, shipment_id: str, data: PickupDetails) -> bool:
        request_data = PickupRequest(pickup_details=data)
        response = self._make_api_request(
            f"shipment/{shipment_id}/schedule", "POST", payload=request_data
        )
        if response:
            return True
        return True

    def _del_cancel_shipment(self, shipment_id: str) -> bool:
        # Deletes a known shipment_id. No return from API
        self._make_api_request(f"shipment/{shipment_id}", "DELETE", None)

        # Make sure the shipment is deleted
        status = self._get_shipment_status(shipment_id)
        if status.state != "cancelled":
            raise ValidationError(self.env._("Could not cancel the shipment"))

        return True

    def _del_cancel_scheduling(self, shipment_id: str) -> bool:
        self._make_api_request(f"shipment/{shipment_id}", "DELETE", None)
        return True

    def _get_payment_methods(self) -> list[dict[str, str]]:
        res = self._make_api_request("finance/payment-methods", "GET")
        if isinstance(res, list):
            return res
        else:
            return []

    def _make_origin(
        self, order: StockPicking | SaleOrder, contact: HrEmployee | ResPartner
    ) -> Origin:
        company = order.company_id
        phone, email = self._get_contact_info(order, company)
        try:
            origin = Origin(
                name=company.name,
                address=self._make_address(company),
                phone_number=PhoneNumber(number=phone),
                email_addresses=[email] if email else None,
                contact_name=contact.name,
            )
        except PydanticValidationError as e:
            raise ValidationError(self.env._("Could not create origin \n %s", e)) from e
        return origin

    def _make_current_date(self) -> Date:
        current_date = datetime.now(ZoneInfo("America/Montreal"))
        return Date(
            year=current_date.year, month=current_date.month, day=current_date.day
        )

    def _get_delivery_note(self, record: StockPicking | SaleOrder) -> str | None:
        if isinstance(record, StockPicking):
            note = record.delivery_instructions
        elif isinstance(record, SaleOrder):
            note = record.note
        if not note or note == "":
            note = None
        return note

    def _get_contact_info(
        self, order: StockPicking | SaleOrder, partner: ResPartner | ResCompany
    ) -> tuple[str, str]:
        """Get phone and email with fallback to billing or parent."""
        phone = getattr(partner, "phone", False)
        email = getattr(partner, "email", False)

        # If missing, try billing address (partner_invoice_id)
        if not phone or not email:
            billing = None
            if isinstance(order, SaleOrder):
                billing = order.partner_invoice_id
            elif isinstance(order, StockPicking) and order.sale_id:
                billing = order.sale_id.partner_invoice_id

            if billing and billing != partner:
                phone = phone or billing.phone
                email = email or billing.email

        # If still missing, try parent
        if (not phone or not email) and getattr(partner, "parent_id", False):
            phone = phone or partner.parent_id.phone
            email = email or partner.parent_id.email

        # If still missing, try commercial partner
        if (not phone or not email) and getattr(
            partner, "commercial_partner_id", False
        ):
            phone = phone or partner.commercial_partner_id.phone
            email = email or partner.commercial_partner_id.email

        return phone or "", email or ""

    def _make_destination(self, order: StockPicking | SaleOrder) -> Destination:
        if isinstance(order, SaleOrder):
            client = order.partner_shipping_id
        else:
            client = order.partner_id

        phone, email = self._get_contact_info(order, client)

        note = self._get_delivery_note(order)

        if not phone:
            raise ValidationError(
                self.env._("Could not find phone number for %s", client.name)
            )

        if not email:
            raise ValidationError(
                self.env._("Could not find email for %s", client.name)
            )

        try:
            destination = Destination(
                name=client.name,
                address=self._make_address(client),
                residential=True,
                phone_number=PhoneNumber(number=phone),
                email_addresses=[email],
                contact_name=client.name,
                instructions=note,
            )
        except PydanticValidationError as e:
            raise ValidationError(
                self.env._("Could not create destination \n %s", e)
            ) from e
        else:
            return destination

    def _make_address(self, partner: ResPartner | HrEmployee | ResCompany) -> Address:
        record: ResPartner | ResCompany | None = None

        if isinstance(partner, (ResPartner, ResCompany)):
            record = partner

        elif isinstance(partner, HrEmployee):
            record = partner.company_id

        if not record:
            raise ValidationError(self.env._("Could not make address for %s", partner))

        try:
            address = Address(
                address_line_1=record.street,
                address_line_2=record.street2 or None,
                city=record.city,
                region=record.state_id.code,
                country=record.country_id.code,
                postal_code=record.zip,
            )
        except PydanticValidationError as e:
            raise ValidationError(self.env._("Could not make address. \n %s", e)) from e
        else:
            return address

    def _make_shipping_details(
        self, order: StockPicking | SaleOrder, contact: HrEmployee | ResPartner
    ) -> ShippingDetails:
        origin = self._make_origin(order, contact)
        destination = self._make_destination(order)
        current_date = self._make_current_date()
        packages: list[Package] | None = None
        if isinstance(order, StockPicking):
            packages = [
                self._make_package(package)
                for package in order._get_packages()
                if isinstance(order, StockPicking)
            ]

        if not packages:
            packages = [self._make_package(None)]
        try:
            details = ShippingDetails(
                origin=origin,
                destination=destination,
                expected_ship_date=current_date,
                packaging_type=PackageTypeEnum.package.value,
                packaging_properties=PackagePackagingProperties(packages=packages),
            )
        except PydanticValidationError as e:
            raise ValidationError(
                self.env._("Could not make shipping details. \n %s", e)
            ) from e
        else:
            return details

    def _make_package(self, package: StockPackage | None) -> Package:
        if not package:
            return Package(
                measurements=Box(
                    weight=Weight(unit=WeightUnitEnum.kg.value, value=4.55),
                    cuboid=Cuboid(unit="mm", length=254, width=254, height=254),
                ),
                description="Box",
            )

        w_uom = WeightUnitEnum.kg.value
        match package.weight_uom_name:
            case "lb":
                w_uom = WeightUnitEnum.lb.value
            case "g":
                w_uom = WeightUnitEnum.g.value
            case "oz":
                w_uom = WeightUnitEnum.oz.value
            case _:
                pass

        l_uom = package.package_type_id.length_uom_name or "mm"

        length = package.package_type_id.packaging_length or 254
        width = package.package_type_id.width or 254
        height = package.package_type_id.height or 254

        weight = package.shipping_weight or 4.55

        package_data = Package(
            measurements=Box(
                weight=Weight(unit=w_uom, value=weight),
                cuboid=Cuboid(
                    unit=LengthUnitEnum[l_uom].value,
                    length=length,
                    width=width,
                    height=height,
                ),
            ),
            description=package.package_type_id.name or "Box",
        )
        return package_data

    def _make_pickup_details(self, contact: HrEmployee | ResPartner) -> PickupDetails:
        details = PickupDetails(
            date=self._make_current_date(),
            ready_at=TimeOfDay(hour=11, minute=59),
            ready_until=TimeOfDay(hour=16, minute=0),
            pickup_location="Docks",
            contact_name=contact.name,
            contact_phone_number=PhoneNumber(number=self._get_phone_number(contact)),
        )
        return details

    def _get_phone_number(self, contact: ResPartner | HrEmployee) -> str:
        if isinstance(contact, ResPartner):
            return contact.phone
        elif isinstance(contact, HrEmployee):
            return contact.work_phone

        return ""

    def _make_shipment_request(
        self, order: StockPicking, contact: ResPartner | HrEmployee
    ) -> ShipmentRequest:
        origin_name: str = getattr(order, "origin", "")
        unique_id: str = ""
        if origin_name:
            unique_id = origin_name + "-" + order.name
        else:
            unique_id = order.name

        payment_method = order.carrier_id.clickship_payment_method.code  # type: ignore
        shipping_details = self._make_shipping_details(order, contact)
        pickup_details = self._make_pickup_details(contact)

        request = ShipmentRequest(
            unique_id=unique_id,
            payment_method_id=payment_method,
            service_id=order.clickship_service_id,  # type: ignore
            details=shipping_details,
            pickup_details=pickup_details,
        )
        return request

    def _fetch_label_data(self, url: str) -> str:
        data = urlopen(url, timeout=30)
        return data.read().decode("UTF-8")
