from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import LinkStatus, Origin


class ProductLink(Base):
    __tablename__ = "product_links"
    __table_args__ = (
        UniqueConstraint("product_id", "canonical_product_id", name="uq_link_product_canonical"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="chk_links_confidence"),
        Index("idx_links_canonical", "canonical_product_id"),
        Index("idx_links_status", "status"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("products.id", name="fk_links_product", ondelete="CASCADE"), nullable=False)
    canonical_product_id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), ForeignKey("canonical_products.id", name="fk_links_canonical", ondelete="CASCADE"), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    origin: Mapped[Origin] = mapped_column(Enum(Origin, name="product_link_origin_enum", values_callable=lambda enum: [item.value for item in enum]), nullable=False)
    status: Mapped[LinkStatus] = mapped_column(Enum(LinkStatus, name="product_link_status_enum", values_callable=lambda enum: [item.value for item in enum]), nullable=False, default=LinkStatus.PENDING, server_default=text("'pending'"))
    reasons: Mapped[list[Any] | None] = mapped_column(JSON)
    confirmed_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP"))