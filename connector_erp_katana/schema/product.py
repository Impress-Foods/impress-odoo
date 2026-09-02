from typing import Literal

from pydantic import Field

from .base import BaseKatanaModel


class ProductConfig(BaseKatanaModel):
    name: str
    values: list[str]
    product_id: int


class ProductVariant(BaseKatanaModel):
    product_id: int | None = None
    sku: str | None = None
    internal_barcode: str | None = None
    registered_barcode: str | None = None
    supplier_item_codes: list[str] | None = None


class ProductProduct(BaseKatanaModel):
    name: str
    uom: str
    batch_tracked: bool
    entity_type: Literal["product"] = Field(default="product", alias="type")
    variants: list[ProductVariant]
    configs: list[ProductConfig]
