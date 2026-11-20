from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import ImportStatus
from app.schemas.common import Schema


class ImportCreate(Schema):
    supplier_id: int = Field(gt=0)
    original_filename: str = Field(min_length=1, max_length=255)
    stored_path: str = Field(min_length=1, max_length=500)


class ImportUpdate(Schema):
    status: ImportStatus | None = None
    rows_read: int | None = Field(default=None, ge=0)
    rows_imported: int | None = Field(default=None, ge=0)
    rows_updated: int | None = Field(default=None, ge=0)
    rows_rejected: int | None = Field(default=None, ge=0)
    rejection_report: dict[str, Any] | None = None


class ImportRead(ImportCreate):
    id: int
    status: ImportStatus
    rows_read: int
    rows_imported: int
    rows_updated: int
    rows_rejected: int
    rejection_report: dict[str, Any] | None
    created_at: datetime