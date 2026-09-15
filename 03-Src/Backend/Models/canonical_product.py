from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from Backend.database import Base


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stock_in_bodega: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
