from ..schema.contact import Address, Contact
from ..schema.product import ProductConfig, ProductProduct, ProductVariant


def mock_contact(
    record_id: int = 1,
    name: str = "John Doe",
    company: str = "Company & co",
    email: str = "john@example.com",
    phone: str = "55-1234",
    first_name: str = "John",
    last_name: str = "Doe",
    addresses: list[Address] | None = None,
) -> Contact:
    if addresses is None:
        addresses = [mock_address()]

    return Contact(
        id=record_id,
        name=name,
        company=company,
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        addresses=addresses,
    )


def mock_address(
    record_id: int = 1,
    customer_id: int = 1,
    first_name: str | None = "Test",
    last_name: str | None = "McTest",
    line_1: str = "123 Test Lane",
    line_2: str | None = None,
    city: str | None = "TestVille",
    state: str | None = "QC",
    country: str | None = "ca",
    zip_code: str | None = "I1I 1I1",
    entity_type: str = "shipping",
    phone: str | None = "(123) 123-1234",
) -> Address:
    """Factory for mock Katana Address"""
    return Address(
        id=record_id,
        customer_id=customer_id,
        first_name=first_name,
        last_name=last_name,
        line_1=line_1,
        line_2=line_2,
        city=city,
        state=state,
        country=country,
        zip=zip_code,
        entity_type=entity_type,
        phone=phone,
    )


def mock_product_config() -> ProductConfig:
    pass


def mock_product_variant() -> ProductVariant:
    pass


def mock_product(
    record_id: int = 1,
    name: str = "Product A",
    uom: str | None = "Pieces",
    batch_tracked: bool = True,
    variants: list[ProductVariant] | None = None,
    configs: list[ProductConfig] | None = None,
) -> ProductProduct:
    variants = variants or [mock_product_variant()]
    configs = configs or [mock_product_config()]

    return ProductProduct(
        id=record_id,
        name=name,
        uom=uom,
        batch_tracked=batch_tracked,
        variants=variants,
        configs=configs,
    )
