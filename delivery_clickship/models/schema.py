from enum import Enum

from pydantic import AliasChoices, BaseModel, Field


class TimeOfDay(BaseModel):
    hour: int
    minute: int


class Date(BaseModel):
    year: int
    month: int
    day: int


class SignatureRequirementEnum(str, Enum):
    not_required = "not-required"
    required = "required"
    adult_required = "adult-required"


class PackageTypeEnum(str, Enum):
    pallet = "pallet"
    package = "package"
    courier_pak = "courier-pak"
    envelope = "envelope"


class ShipmentStateEnum(str, Enum):
    draft = "draft"
    waiting = "waiting-for-transit"
    transit = "in-transit"
    delivered = "delivered"
    exception = "exception"
    missing = "missing"
    cancelled = "cancelled"


class WeightUnitEnum(str, Enum):
    kg = "kg"
    lb = "lb"
    g = "g"
    oz = "oz"


class LengthUnitEnum(str, Enum):
    mm = "mm"
    cm = "cm"
    m = "m"
    inch = "in"
    ft = "ft"


class Money(BaseModel):
    currency: str = "CAD"
    value: str = "0000"


class Address(BaseModel):
    address_line_1: str = Field(
        validation_alias=AliasChoices("address_line_1", "address_line1")
    )
    address_line_2: str | None = Field(
        default=None, validation_alias=AliasChoices("address_line_2", "address_line2")
    )
    unit_number: str | None = None
    city: str
    region: str
    country: str
    postal_code: str


class PhoneNumber(BaseModel):
    number: str
    extension: str = ""


class Origin(BaseModel):
    name: str = ""
    address: Address
    residential: bool = False
    instructions: str | None = None
    contact_name: str
    phone_number: PhoneNumber = PhoneNumber(number="")
    email_addresses: list[str] | None = None


class Destination(BaseModel):
    name: str = ""
    address: Address
    residential: bool = True
    instructions: str | None = None
    contact_name: str | None = None
    phone_number: PhoneNumber | None = PhoneNumber(number="")
    email_addresses: list[str] | None = None
    ready_at: TimeOfDay = TimeOfDay(hour=8, minute=0)
    ready_until: TimeOfDay = TimeOfDay(hour=16, minute=30)
    signature_requirement: str = SignatureRequirementEnum.not_required.value


class Weight(BaseModel):
    unit: str
    value: float


class Cuboid(BaseModel):
    unit: str
    l: float  # noqa
    w: float  # noqa
    h: float  # noqa


class Box(BaseModel):
    weight: Weight
    cuboid: Cuboid


class Package(BaseModel):
    measurements: Box
    description: str
    special_handling_required: bool = False


class PackagePackagingProperties(BaseModel):
    includes_return_label: bool = False
    has_dangerous_goods: bool = False
    packages: list[Package]


class Fee(BaseModel):
    fee_type: str = Field(validation_alias=AliasChoices("fee_type", "type"))
    amount: Money


class PalletPackagingProperties(BaseModel):
    # TODO: Implement
    pass


class ShippingDetails(BaseModel):
    origin: Origin
    destination: Destination
    expected_ship_date: Date
    packaging_type: str = PackageTypeEnum.package.value
    packaging_properties: PackagePackagingProperties | PalletPackagingProperties


class RateRequestData(BaseModel):
    services: list[str] | None = None
    excluded_services: list[str] | None = None
    details: ShippingDetails


class Rate(BaseModel):
    carrier_name: str
    service_name: str
    service_id: str
    valid_until: Date
    total: Money
    base: Money
    surcharges: list[Fee]
    taxes: list[Fee]
    transit_time_days: int
    transit_time_not_available: bool


class RateStatus(BaseModel):
    done: bool
    total: int = 0
    complete: int = 0


class RateResponse(BaseModel):
    status: RateStatus
    rates: list[Rate]


class PickupDetails(BaseModel):
    pre_scheduled_pickup: bool = False
    date: Date
    ready_at: TimeOfDay
    ready_until: TimeOfDay
    pickup_location: str
    contact_name: str
    contact_phone_number: PhoneNumber


class PickupRequest(BaseModel):
    pickup_details: PickupDetails


class ShipmentRequest(BaseModel):
    unique_id: str
    payment_method_id: str
    service_id: str
    details: ShippingDetails
    pickup_details: PickupDetails
    dispatch_details: None = None
    customs_invoice: None = None


class Shipment(BaseModel):
    id: str
    unique_id: str
    state: str
    transaction_number: str
    primary_tracking_number: str
    tracking_numbers: list[str]
    tracking_url: str
    return_tracking_number: str | None
    bol_number: str = ""
    picking_confirmation_number: str = ""
    details: ShippingDetails
    transport_data: dict | None = None
    labels: list[dict] | None = None
    customs_invoice_url: str | None = None
    rate: Rate
    order_source: str
