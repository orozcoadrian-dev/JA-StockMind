from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from Backend.database import Base


class ProductLink(Base):
    __tablename__ = "product_links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    canonical_product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id"), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    origin: Mapped[str] = mapped_column(String(50), nullable=False, default="suggestion")
    confirmed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
