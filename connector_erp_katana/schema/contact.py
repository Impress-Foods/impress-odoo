from typing import Literal

from pydantic import Field

from .base import BaseKatanaModel


class Address(BaseKatanaModel):
    entity_type: Literal["billing", "shipping"]
    customer_id: int
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    phone: str | None = None
    line_1: str | None = None
    line_2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip_code: str | None = Field(alias="zip", default=None)


class Contact(BaseKatanaModel):
    name: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    email: str | None = None
    reference_id: str | None = None
    category: str | None = None
    currency: str | None = None
    phone: str | None = None
    addresses: list[Address] | None = None
