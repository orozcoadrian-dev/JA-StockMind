from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "row_hash", name="uq_products_supplier_hash"),
        Index("idx_products_normalized_name", "normalized_name"),
        Index("idx_products_supplier_code", "supplier_id", "supplier_code"),
        Index("idx_products_category", "category_id"),
        Index("idx_products_import", "import_id"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("suppliers.id", name="fk_products_supplier"), nullable=False)
    import_id: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("imports.id", name="fk_products_import", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("categories.id", name="fk_products_category", ondelete="SET NULL"))
    supplier_code: Mapped[str | None] = mapped_column(String(60))
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="COP", server_default=text("'COP'"))
    unit: Mapped[str | None] = mapped_column(String(20))
    pack_quantity: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=1, server_default=text("1"))
    price_list_date: Mapped[date | None] = mapped_column(Date)
    row_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP"))