from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ChatMessageRole


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_chat_messages_session_seq"),
        Index("idx_chat_messages_session", "session_id"),
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("chat_sessions.id", name="fk_chat_messages_session", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    role: Mapped[ChatMessageRole] = mapped_column(
        Enum(
            ChatMessageRole,
            name="chat_message_role_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(mysql.LONGTEXT(), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(60))
    tool_call_id: Mapped[str | None] = mapped_column(String(100))
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    tool_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    agent_action_id: Mapped[int | None] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("agent_actions.id", name="fk_chat_messages_agent_action", ondelete="RESTRICT"),
    )
    model: Mapped[str | None] = mapped_column(String(100))
    tokens_input: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True))
    tokens_output: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
