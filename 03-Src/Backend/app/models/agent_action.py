from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, JSON, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"
    __table_args__ = (
        Index("idx_actions_session", "session_id"),
        Index("idx_actions_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(60), nullable=False)
    input_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    required_confirmation: Mapped[bool] = mapped_column(mysql.TINYINT(display_width=1), nullable=False, default=False, server_default=text("0"))
    approved: Mapped[bool | None] = mapped_column(mysql.TINYINT(display_width=1))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))