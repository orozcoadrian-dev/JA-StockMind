from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.common import Schema


class ProductCreate(Schema):
    supplier_id: int = Field(gt=0)
    import_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    supplier_code: str | None = Field(default=None, max_length=60)
    raw_name: str = Field(min_length=1, max_length=255)
    normalized_name: str = Field(min_length=1, max_length=255)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    currency: str = Field(default="COP", min_length=3, max_length=3)
    unit: str | None = Field(default=None, max_length=20)
    pack_quantity: int = Field(default=1, ge=0)
    price_list_date: date | None = None
    row_hash: str = Field(min_length=64, max_length=64)

    @field_validator("unit_price")
    @classmethod
    def price_must_not_be_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("El precio unitario no puede ser negativo.")
        return value


class ProductUpdate(Schema):
    supplier_id: int | None = Field(default=None, gt=0)
    import_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    supplier_code: str | None = Field(default=None, max_length=60)
    raw_name: str | None = Field(default=None, min_length=1, max_length=255)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=255)
    unit_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    unit: str | None = Field(default=None, max_length=20)
    pack_quantity: int | None = Field(default=None, ge=0)
    price_list_date: date | None = None
    row_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("unit_price")
    @classmethod
    def price_must_not_be_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("El precio unitario no puede ser negativo.")
        return value


class ProductRead(ProductCreate):
    id: int
    created_at: datetime
    updated_at: datetime