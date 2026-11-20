from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Index, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ChatSessionStatus


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("uq_chat_sessions_external_id", "external_id", unique=True),
        Index("idx_chat_sessions_last_message", "last_message_at"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid4()))
    title: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[ChatSessionStatus] = mapped_column(
        Enum(
            ChatSessionStatus,
            name="chat_session_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ChatSessionStatus.ACTIVE,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    message_count: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
