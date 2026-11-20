from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ImportStatus


class Import(Base):
    __tablename__ = "imports"
    __table_args__ = (Index("idx_imports_supplier", "supplier_id"),)

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("suppliers.id", name="fk_imports_supplier"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus, name="import_status_enum", values_callable=lambda enum: [item.value for item in enum]), nullable=False, default=ImportStatus.PROCESSING, server_default=text("'processing'"))
    rows_read: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default=text("0"))
    rows_imported: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default=text("0"))
    rows_updated: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default=text("0"))
    rows_rejected: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default=text("0"))
    rejection_report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))