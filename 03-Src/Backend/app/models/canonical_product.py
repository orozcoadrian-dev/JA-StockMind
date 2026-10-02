from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"
    __table_args__ = (
        Index("idx_canonical_name", "canonical_name"),
        Index("idx_canonical_category", "category_id"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("categories.id", name="fk_canonical_category", ondelete="SET NULL"))
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    min_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP"))