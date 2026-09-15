from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from Backend.database import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
