from typing import Any, NamedTuple

from odoo.addons.base.models.res_company import Company
from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.product.models.uom_uom import UoM
from odoo.addons.stock.models.stock_location import Location


class Procurement(NamedTuple):
    """
    Type alias for the Procurement namedtuple used in Odoo.
    """

    product_id: ProductProduct
    product_qty: float
    product_uom: UoM
    location_id: Location
    name: str
    origin: str
    company_id: Company
    values: dict[str, Any]
