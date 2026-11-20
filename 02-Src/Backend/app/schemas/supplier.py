from datetime import datetime

from pydantic import Field

from app.schemas.common import Schema


class SupplierCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    contact: str | None = Field(default=None, max_length=150)
    active: bool = True


class SupplierUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    contact: str | None = Field(default=None, max_length=150)
    active: bool | None = None


class SupplierRead(SupplierCreate):
    id: int
    created_at: datetime