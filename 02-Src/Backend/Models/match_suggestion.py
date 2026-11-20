from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from Backend.database import Base


class MatchSuggestion(Base):
    __tablename__ = "match_suggestions"
    __table_args__ = (
        UniqueConstraint("product_id", "candidate_product_id", name="uq_match_suggestion_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    candidate_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="review")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)