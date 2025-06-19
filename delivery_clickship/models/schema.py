from enum import Enum

from pydantic import BaseModel


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
    address_line_1: str
    address_line_2: str | None = None
    unit_number: str | None = None
    city: str
    region: str
    country: str
    postal_code: str


class PhoneNumber(BaseModel):
    number: str
    extension: str | None = None


class Origin(BaseModel):
    name: str = ""
    address: Address
    residential: bool = False
    instructions: str | None = None
    contact_name: str | None = None
    phone_number: PhoneNumber = PhoneNumber(number="")
    email_addresses: list[str] | None = None


class Destination(BaseModel):
    name: str = ""
    address: Address
    residential: bool = True
    instructions: str | None = None
    contact_name: str | None = None
    phone_number: PhoneNumber = PhoneNumber(number="")
    email_addresses: list[str] | None = None
    ready_at: TimeOfDay = TimeOfDay(hour=8, minute=0)
    ready_until: TimeOfDay = TimeOfDay(hour=8, minute=0)
    signature_requirement: SignatureRequirementEnum = (
        SignatureRequirementEnum.not_required
    )


class Weigth(BaseModel):
    unit: WeightUnitEnum
    value: float


class Cuboid(BaseModel):
    unit: LengthUnitEnum
    l: float  # noqa
    w: float  # noqa
    h: float  # noqa


class Box(BaseModel):
    weigth: Weigth
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
    fee_type: str
    amount: Money


class PalletPackagingProperties(BaseModel):
    # TODO: Implement
    pass


class ShipmentDetails(BaseModel):
    origin: Origin
    destination: Destination
    expected_ship_date: Date
    packaging_type: PackageTypeEnum = PackageTypeEnum.package
    packaging_properties: PackagePackagingProperties | PalletPackagingProperties


class RateRequestData(BaseModel):
    services: list[str] | None = None
    excluded_services: list[str] | None = None
    details: ShipmentDetails


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
    tansit_time_not_available: bool


class RateStatus(BaseModel):
    done: bool
    total: int
    complete: int
    rates: list[Rate]


class PickupDetails(BaseModel):
    pre_scheduled_pickup: bool = False
    date: Date
    ready_at: TimeOfDay
    ready_until: TimeOfDay
    pickup_locations: str
    contact_name: str
    contact_phone_number: str


class Shipment(BaseModel):
    unique_id: str
    payment_method_id: str
    service_id: str
    details: ShipmentDetails
    pickup_details: PickupDetails
