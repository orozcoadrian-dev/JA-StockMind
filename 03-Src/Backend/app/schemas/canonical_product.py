from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import Schema


class CanonicalProductCreate(Schema):
    canonical_name: str = Field(min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    attributes: dict[str, Any] | None = None
    stock: int = 0
    min_stock: int = 0


class CanonicalProductUpdate(Schema):
    canonical_name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    attributes: dict[str, Any] | None = None
    stock: int | None = None
    min_stock: int | None = None


class CanonicalProductRead(CanonicalProductCreate):
    id: int
    created_at: datetime
    updated_at: datetime