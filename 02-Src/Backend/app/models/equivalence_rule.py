from datetime import datetime
from typing import Any

from sqlalchemy import Enum, Index, Integer, JSON, Text, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RuleType


class EquivalenceRule(Base):
    __tablename__ = "equivalence_rules"
    __table_args__ = (Index("idx_rules_type_active", "rule_type", "active"),)

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType, name="equivalence_rule_type_enum", values_callable=lambda enum: [item.value for item in enum]), nullable=False)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    suppliers: Mapped[list[Any] | None] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(mysql.TINYINT(display_width=1), nullable=False, default=True, server_default=text("1"))
    times_applied: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("CURRENT_TIMESTAMP"))