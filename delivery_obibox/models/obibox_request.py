import json
import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth
from werkzeug.urls import url_join

from odoo import _
from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_company import Company  # noqa
from odoo.addons.base.models.res_partner import Partner  # noqa
from odoo.addons.sale.models.sale_order import SaleOrder  # noqa
from odoo.addons.stock.models.stock_picking import Picking  # noqa
from odoo.addons.stock.models.stock_quant import QuantPackage  # noqa
from odoo.addons.uom.models.uom_uom import UoM  # noqa

from .schema import (
    Box,
    BoxesDimensions,
    Rate,
    RateRequest,
    ShippingRequestMulti,
    Tracking,
)

_logger = logging.getLogger(__name__)

days = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}


class ObiboxProvider:
    def __init__(
        self,
        debug_logger,
        prod_environment: bool = False,
        username: str = "",
        token: str = "",
    ):
        self.debug_logger = debug_logger
        self.session = requests.Session()
        self.username = username
        self.token = token

        if not prod_environment:
            self.url = "https://integrationapi.sandbox.agmtsolution.com/api/"
        else:
            self.url = "https://api.obibox.com"

    def check_coverage(self, partner: Partner) -> bool:
        zip_code = partner.zip
        if not zip_code:
            raise ValidationError(f"Could not find zip code for partner {partner.name}")

        response = self._make_api_request(f"Order/GetServices/{zip_code}", "GET")
        if isinstance(response, dict) and response.get("errors", False):
            return False
        if not response:
            return False
        return True

    def get_rate(self, order: SaleOrder | Picking) -> dict:
        data = self._make_rate_request(order)
        res = self._get_rate(data)

        return {
            "success": True,
            "price": res.price_in_cad,
            "error_message": False,
            "warning_message": False,
        }

    def book_shipment(self, picking: Picking) -> dict[str, Any]:
        rate_request = self._make_rate_request(picking)
        rate = self._get_rate(rate_request)
        price = rate.price_in_cad if rate else 0
        data = self._make_shipment_request(picking)

        label_format = picking.carrier_id.obibox_label_format

        params = {"withWaybill": True}

        if label_format == "zpl":
            params["pdf"] = False
            params["zpl"] = True
        else:
            params["pdf"] = True
            params["zpl"] = False

        response = self._make_api_request(
            "Order/PostOrderMulti", method="POST", payload=data, params=params
        )

        trackings = [Tracking.model_validate(tracking) for tracking in response]

        res = {
            "exact_price": price,
            "tracking_number": trackings[0].tracking_number,
            "label_data": "".join([x.waybill for x in trackings]),
            "trackings": trackings,
        }
        return res

    def cancel_shipment(self, picking: Picking) -> bool:
        trackings = picking.obibox_tracking_numbers.split(",")
        for tracking in trackings:
            res = self._cancel_shipment(tracking)
            if isinstance(res, str):
                raise ValidationError(_(f"Could not cancel shipment: {res}"))
        return True

    def _make_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: None | dict | BaseModel | str = None,
        params: None | dict = None,
    ):
        if not payload:
            payload = {}

        auth = HTTPBasicAuth(self.username, self.token)
        headers = {"Content-Type": "application/json"}
        access_url = url_join(self.url, endpoint)

        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True, by_alias=True)

        try:
            self.debug_logger(
                f"{access_url} {method} \n {payload}",
                f"clickship_request_{endpoint}",
            )
            match method:
                case "GET":
                    response = self.session.get(
                        access_url,
                        params=params,
                        auth=auth,
                        headers=headers,
                        timeout=30,
                    )
                case "POST":
                    response = self.session.post(
                        access_url,
                        params=params,
                        json=payload,
                        auth=auth,
                        headers=headers,
                        timeout=30,
                    )
                case "DELETE":
                    response = self.session.delete(
                        access_url,
                        params=params,
                        data=payload,
                        auth=auth,
                        headers=headers,
                        timeout=30,
                    )
                case _:
                    _logger.warning(f"Unsupported method: {method}")
                    return {"errors": {"method": f"Unsupported method: {method}"}}

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

    def _get_rate(self, data: RateRequest) -> Rate:
        endpoint = "Order/GetRatesPerServices"

        response = self._make_api_request(endpoint, method="POST", payload=data)
        res = Rate.model_validate(response[0])  # type: ignore
        return res

    def _cancel_shipment(self, tracking: str) -> bool | str:
        res = self._make_api_request(f"Order/{tracking}", "DELETE")
        if isinstance(res, dict) and res.get("errors"):
            return res["errors"]
        return True

    def _get_postal_code(self, order: SaleOrder | Picking) -> str:
        if isinstance(order, SaleOrder):
            return order.partner_shipping_id.zip or ""
        elif isinstance(order, Picking):
            return order.partner_id.zip or ""
        else:
            _logger.error("Unsupported order type for postal code extraction.")
            return ""

    def _make_package(self, package: QuantPackage) -> tuple[Box, BoxesDimensions]:
        box = Box()
        package_type = package.package_type_id

        feet: UoM = package.env["uom.uom"].search([("name", "=", "ft")])[0]
        inches: UoM = package.env["uom.uom"].search([("name", "=", "in")])[0]
        pounds: UoM = package.env["uom.uom"].search([("name", "=", "lb")])[0]

        length_uom: UoM = package.env["uom.uom"].search(
            [("name", "=", package_type.length_uom_name)]
        )[0]
        weight_uom: UoM = package.env["uom.uom"].search(
            [("name", "=", package_type.weight_uom_name)]
        )[0]

        length_in = length_uom._compute_quantity(package_type.packaging_length, inches)
        width_in = length_uom._compute_quantity(package_type.width, inches)
        height_in = length_uom._compute_quantity(package_type.height, inches)

        length_ft = length_uom._compute_quantity(package_type.packaging_length, feet)
        width_ft = length_uom._compute_quantity(package_type.width, feet)
        height_ft = length_uom._compute_quantity(package_type.height, feet)

        volume = length_ft * width_ft * height_ft
        long_side = max(length_in, width_in, height_in)

        shipping_weight = weight_uom._compute_quantity(package.shipping_weight, pounds)

        dimensions = BoxesDimensions(
            weight=shipping_weight,
            volume=volume,
            long_side=long_side,
        )
        return box, dimensions

    def _make_address(self, contact: Partner | Company) -> dict[str, str]:
        return {
            "address1": contact.street or "",
            "address2": contact.street2 or "",
            "city": contact.city or "",
            "province": contact.state_id.code if contact.state_id else "",
            "postal_code": contact.zip or "",
        }

    def _make_shipment_request(self, picking) -> ShippingRequestMulti:
        from_address = self._make_address(picking.company_id.partner_id)
        to_address = self._make_address(picking.partner_id)
        boxes = []
        dims = []
        for package in picking.package_ids:
            box, dim = self._make_package(package)
            boxes.append(box)
            dims.append(dim)

        total_weight = sum(map(lambda x: x.weight, dims))

        pickup_date = self._get_pickup_date(
            picking.date_done, picking.carrier_id.obibox_delivery_day
        )

        data = ShippingRequestMulti(
            order_ref_number=self._get_order_ref(picking),
            from_address1=from_address["address1"],
            from_address2=from_address["address2"],
            from_city=from_address["city"],
            from_province=from_address["province"],
            from_postal_code=from_address["postal_code"],
            to_address1=to_address["address1"],
            to_address2=to_address["address2"],
            to_city=to_address["city"],
            to_province=to_address["province"],
            to_postal_code=to_address["postal_code"],
            client_name=picking.partner_id.name or "",
            name=picking.partner_id.name or "",
            phone=picking.partner_id.phone or "",
            email=picking.partner_id.email or "",
            instructions=picking.note or "",
            b2b="1" if picking.partner_id.is_company else "0",
            nb_items=len(boxes),
            delivery_date_time=pickup_date + timedelta(days=1),
            service="NEXTDAY",
            weight=total_weight,
            boxes=boxes,
            boxes_dimensions=dims,
        )
        return data

    def _get_order_ref(self, operation: SaleOrder | Picking) -> str:
        ref = ""
        if isinstance(operation, SaleOrder):
            ref = operation.name
        elif isinstance(operation, Picking):
            if operation.origin:
                ref = operation.origin
            else:
                ref = operation.name
        else:
            _logger.error("Unsupported operation type for order reference extraction.")
            return ""

        return ref.replace("/", "")

    def _make_rate_request(self, order: SaleOrder | Picking) -> RateRequest:
        if isinstance(order, Picking):
            boxes = []
            boxes_dimensions = []
            for package in order.package_ids:
                box, dim = self._make_package(package)
                boxes.append(box)
                boxes_dimensions.append(dim)

        else:
            boxes = [Box()]
            boxes_dimensions = [
                BoxesDimensions(
                    weight=5,
                    volume=0.578704,
                    long_side=10,
                )
            ]

        data = RateRequest(
            from_postal_code=order.company_id.zip,
            to_postal_code=self._get_postal_code(order),
            boxes=boxes,
            boxes_dimensions=boxes_dimensions,
        )
        return data

    def _get_pickup_date(self, picking_date: datetime, delivery_day: str) -> datetime:
        next_delivery_day = picking_date + relativedelta(weekday=days[delivery_day])
        return next_delivery_day
