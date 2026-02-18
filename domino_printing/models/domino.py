import logging

import requests
from pydantic import BaseModel
from werkzeug.urls import url_join

from .schema import DominoProduct

_logger = logging.getLogger(__name__)


class DominoAPI:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self.session = requests.Session()

    def _make_api_request(
        self, endpoint: str, method: str = "GET", payload: BaseModel | None = None
    ) -> dict:
        access_url = url_join(self.url, endpoint)
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}
        json_payload = payload.model_dump(exclude_none=True)
        try:
            match method:
                case "GET":
                    response = self.session.get(access_url, headers=headers, timeout=30)
                case "POST":
                    response = self.session.post(
                        access_url,
                        headers=headers,
                        json=json_payload,
                        timeout=30,
                    )
        except requests.exceptions.ConnectionError as error:
            _logger.warning(
                f"Connection Error: {error} with the given URL: {access_url}"
            )
            return {
                "errors": {
                    "timeout": "Cannot reach the server. Please try again later."
                }
            }
        return response

    def sync_product(self, product) -> None:
        payload: DominoProduct = DominoProduct(
            OdooProductID=product.id,
            ProductCode=product.default_code if product.default_code else None,
            Barcode=product.barcode if product.barcode else None,
            ProductName=product.domino_name if product.domino_name else None,
        )
        if product.product_tmpl_id.use_expiration_date:
            payload.ShelfLifeDays = product.product_tmpl_id.expiration_time

        response = self._make_api_request("/products", method="POST", payload=payload)
        _logger.warning(response)
