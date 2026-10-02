from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.models.enums import LinkStatus, Origin
from app.schemas.common import Schema


class ProductLinkCreate(Schema):
    product_id: int = Field(gt=0)
    canonical_product_id: int = Field(gt=0)
    confidence: Decimal = Field(max_digits=4, decimal_places=3)
    origin: Origin
    status: LinkStatus = LinkStatus.PENDING
    reasons: list[Any] | None = None
    confirmed_by: str | None = Field(default=None, max_length=80)

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, value: Decimal) -> Decimal:
        if not Decimal("0") <= value <= Decimal("1"):
            raise ValueError("La confianza debe estar entre 0 y 1.")
        return value


class ProductLinkUpdate(Schema):
    confidence: Decimal | None = Field(default=None, max_digits=4, decimal_places=3)
    origin: Origin | None = None
    status: LinkStatus | None = None
    reasons: list[Any] | None = None
    confirmed_by: str | None = Field(default=None, max_length=80)

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not Decimal("0") <= value <= Decimal("1"):
            raise ValueError("La confianza debe estar entre 0 y 1.")
        return value


class ProductLinkRead(ProductLinkCreate):
    id: int
    created_at: datetime
    updated_at: datetime