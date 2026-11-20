from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from .. import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("supplier_id", "supplier_code", "price_list_date", name="uq_product_supplier_code_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="COP", nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)
    pack_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price_list_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_row_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    supplier: Mapped["Supplier"] = relationship(back_populates="products")
    links: Mapped[list["ProductLink"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    provider_code = synonym("supplier_code")
    row_hash = synonym("raw_row_hash")