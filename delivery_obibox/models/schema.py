from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class BaseObiboxModel(BaseModel):
    model_config = ConfigDict(validate_by_name=True)


class Box(BaseObiboxModel):
    Large: bool = False
    OverSize: bool = False
    ShipTo80: bool = False


class BoxesDimensions(BaseObiboxModel):
    weight: float = Field(serialization_alias="WeightInPounds")
    volume: float = Field(serialization_alias="CubicFeet")
    long_side: float = Field(serialization_alias="LongerSideInInches")


class RateRequest(BaseObiboxModel):
    from_postal_code: str = Field(serialization_alias="FromPostalCode")
    to_postal_code: str = Field(serialization_alias="ToPostalCode")
    boxes: list[Box] = Field(serialization_alias="Boxes")
    boxes_dimensions: BoxesDimensions = Field(serialization_alias="BoxesDimensions")
    hand_to_hand: bool = Field(serialization_alias="HandToHand", default=False)
    hth_age_verified: bool = Field(serialization_alias="HTHAgeVerified", default=False)


class Rate(BaseObiboxModel):
    service_name: str = Field(validation_alias="ServiceName")
    pickup_eta: datetime = Field(validation_alias="PickupETA")
    delivery_eta: datetime = Field(validation_alias="DeliveryETA")
    price_in_cad: float = Field(validation_alias="PriceInCAD")

    @field_validator("pickup_eta", "delivery_eta", mode="before")
    @classmethod
    def parse_date(cls, value: str | datetime) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value


class ShippingRequestMulti(BaseObiboxModel):
    order_ref_number: str = Field(serialization_alias="Order_Ref_Number")
    from_address1: str = Field(serialization_alias="From_Address1")
    from_address2: str = Field(serialization_alias="From_Address2", default="")
    from_city: str = Field(serialization_alias="From_City")
    from_province: str = Field(serialization_alias="From_Prov")
    from_postal_code: str = Field(serialization_alias="From_PostalCode")

    to_address1: str = Field(serialization_alias="To_Address1")
    to_address2: str = Field(serialization_alias="To_Address2", default="")
    to_city: str = Field(serialization_alias="To_City")
    to_province: str = Field(serialization_alias="To_Prov")
    to_postal_code: str = Field(serialization_alias="To_PostalCode")

    name: str = Field(serialization_alias="Name")
    phone: str = Field(serialization_alias="Phone")
    email: str = Field(serialization_alias="Email")
    instructions: str = Field(serialization_alias="Deliv_Inst", default="")

    b2b: str = Field(serialization_alias="B2B", default="1")
    nb_items: int = Field(serialization_alias="Nb_Items", default=1)
    delivery_date_time: datetime = Field(serialization_alias="Delivery_Date_Time")
    service: str = Field(serialization_alias="Service", default="NEXTDAY")

    client_name: str = Field(serialization_alias="Client_Name")
    group_name: str = Field(serialization_alias="Group_Name", default="")
    client_tracking_numbers: list[str] = Field(
        serialization_alias="ClientTrackingNumbers", default=[]
    )
    weight: float = Field(serialization_alias="WeightInPounds")
    boxes: list[Box] = Field(serialization_alias="Boxes")
    boxes_dimensions: list[BoxesDimensions] = Field(
        serialization_alias="BoxesDimensions"
    )
    hand_to_hand: bool = Field(serialization_alias="HandToHand", default=False)
    hth_age_verified: bool = Field(serialization_alias="HTHAgeVerified", default=False)

    @field_serializer("delivery_date_time")
    def serialize_delivery_date_time(self, delivery_date_time: datetime):
        return delivery_date_time.strftime("%Y-%m-%dT%H:%M:%S")


class Tracking(BaseObiboxModel):
    hub: str = Field(validation_alias="Hub")
    route_code: str = Field(validation_alias="RouteCode")
    tracking_number: str = Field(validation_alias="TrackingNumber")
    waybill: str = Field(validation_alias="Waybill")


class Service(BaseObiboxModel):
    service_name: str = Field(serialization_alias="ServiceName")
    service_code: str = Field(serialization_alias="ServiceCode")
    service_description: str = Field(serialization_alias="ServiceDescription")
    estimated_time_of_delivery: datetime = Field(
        serialization_alias="EstimatedTimeOfDelivery"
    )

    @field_validator("estimated_time_of_delivery", mode="before")
    @classmethod
    def parse_estimated_time_of_delivery(cls, value: str | datetime) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
