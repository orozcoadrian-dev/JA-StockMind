from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from Backend.database import Base


class EquivalenceRule(Base):
    __tablename__ = "equivalence_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    original_text: Mapped[str] = mapped_column(String(500), nullable=False)
    structured_condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    supplier_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    applied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
