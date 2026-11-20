from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from .. import Base


class ProductLink(Base):
    __tablename__ = "product_links"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_product_link_confidence"),
        CheckConstraint(
            "link_source IN ('rule', 'agent_suggestion', 'manual_confirmation')",
            name="ck_product_link_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    link_source: Mapped[str] = mapped_column(String(30), default="agent_suggestion", nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="links")
    canonical_product: Mapped["CanonicalProduct"] = relationship(back_populates="links")
    confidence = synonym("confidence_score")
    origin = synonym("link_source")