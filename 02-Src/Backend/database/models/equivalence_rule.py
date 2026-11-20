from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, synonym

from .. import Base


class EquivalenceRule(Base):
    __tablename__ = "equivalence_rules"
    __table_args__ = (CheckConstraint("rule_type IN ('equivalence', 'exclusion', 'supplier_preference')", name="ck_rule_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_prompt_text: Mapped[str] = mapped_column(String(500), nullable=False)
    structured_condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    suppliers_involved: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, default="equivalence", index=True)
    times_applied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    original_text = synonym("raw_prompt_text")
    supplier_names = synonym("suppliers_involved")
    active = synonym("is_active")
    applied_count = synonym("times_applied")