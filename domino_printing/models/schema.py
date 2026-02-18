from pydantic import BaseModel


class DominoProduct(BaseModel):
    OdooProductID: int
    ProductCode: str | None = None
    ProductName: str | None = None
    Barcode: str | None = None
    ShelfLifeDays: int | None = None
    LabelText1: str | None = None
    LabelText2: str | None = None
    LabelText3: str | None = None
    Extra1: str | None = None
    Extra2: str | None = None
    Extra3: str | None = None
