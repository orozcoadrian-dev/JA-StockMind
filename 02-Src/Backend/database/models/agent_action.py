from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, synonym

from .. import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    tool_used: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    input_params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    execution_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_approved: Mapped[bool | None] = mapped_column(Boolean)

    tool_name = synonym("tool_used")
    input_payload = synonym("input_params")
    result = synonym("execution_result")
    required_confirmation = synonym("requires_confirmation")
    approved = synonym("is_approved")