import json
from datetime import datetime
from logging import getLogger

from odoo.exceptions import ValidationError
from odoo.tools.translate import LazyTranslate as _

from odoo.addons.connector_erp.models.erp_backend import ERPBackend

from ..schema.base import BaseKatanaModel
from ..schema.contact import Contact
from ..schema.product import ProductProduct

_CUSTOMERS_PAGE_SIZE = 250
_MAX_PAGES = 100
_ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_logger = getLogger(__name__)


def _is_last_page(response) -> bool:
    """Detect whether the paginated Katana response is the final page."""
    link = response.headers.get("Link")
    if link and 'rel="next"' in link:
        return False

    pagination = response.headers.get("X-Pagination")
    if pagination:
        try:
            meta = json.loads(pagination)
            if meta.get("last_page"):
                return True
            return meta.get("page", 1) >= meta.get("total_pages", 1)
        except (ValueError, TypeError) as e:
            _logger.warning(e)

    # No next link and no pagination metadata -> assume single/final page
    return True


class KatanaAPIClient:
    def __init__(self, backend: ERPBackend):
        self.backend = backend

    def fetch_all_customers(
        self, updated_after: datetime | None = None
    ) -> list[Contact]:
        page = 1
        params: dict[str, object] = {"limit": _CUSTOMERS_PAGE_SIZE, "page": page}
        if updated_after:
            params["updated_at_min"] = updated_after.strftime(_ISO_UTC_FORMAT)

        customers: list[Contact] = self.fetch_with_pagination(
            "customers", params, Contact
        )

        return customers

    def fetch_all_products(self) -> list[ProductProduct]:
        products: list[ProductProduct] = self.fetch_with_pagination(
            "products", {}, ProductProduct
        )
        return products

    def fetch_with_pagination(
        self, path, params, model: BaseKatanaModel
    ) -> list[BaseKatanaModel]:
        records: list[BaseKatanaModel] = []

        page = 1
        while True:
            if page > _MAX_PAGES:
                raise ValidationError(_("Katana: pagination exceeded 100 pages"))

            params["page"] = page
            result = self.backend._request_get(path, params=params)
            records.extend(model.model_validate(c) for c in self._extract_data(result))

            if _is_last_page(result):
                break
            page += 1

        return records

    @staticmethod
    def _extract_data(result) -> list[dict]:
        body = result.json()

        if isinstance(body, dict):
            data = body.get("data")
        elif isinstance(body, list):
            data = body
        else:
            raise ValidationError(
                _("Katana: unexpected response type: %(t)s", t=type(body).__name__)
            )

        if data is None:
            raise ValidationError(
                _("Katana: unexpected response shape: %(body)s", body=body)
            )

        return data
