from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentMemoryFactStatus


class AgentMemoryFact(Base):
    __tablename__ = "agent_memory_facts"
    __table_args__ = (
        Index("idx_agent_memory_facts_status_updated", "status", "updated_at"),
        Index("idx_agent_memory_facts_source_session", "source_session_id"),
        Index("idx_agent_memory_facts_source_message", "source_message_id"),
    )

    id: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column("key", String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_session_id: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("chat_sessions.id", name="fk_agent_memory_facts_session", ondelete="RESTRICT"),
        nullable=False,
    )
    source_message_id: Mapped[int | None] = mapped_column(
        mysql.INTEGER(unsigned=True),
        ForeignKey("chat_messages.id", name="fk_agent_memory_facts_message", ondelete="SET NULL"),
    )
    status: Mapped[AgentMemoryFactStatus] = mapped_column(
        Enum(
            AgentMemoryFactStatus,
            name="agent_memory_fact_status_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
