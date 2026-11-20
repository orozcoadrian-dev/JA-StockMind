from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatMessageRole, ChatSession, ChatSessionStatus


class SessionNotFoundError(LookupError):
    def __init__(self, external_id: str):
        self.external_id = external_id
        super().__init__(f"La sesión de chat '{external_id}' no existe.")


class PersistentMemory:
    def __init__(self, db: Session, max_messages: int | None = None):
        self.db = db
        configured_limit = max_messages
        if configured_limit is None:
            configured_limit = int(os.getenv("AGENT_MEMORY_MAX_MESSAGES", "30"))
        if configured_limit < 1:
            raise ValueError("AGENT_MEMORY_MAX_MESSAGES debe ser mayor que cero.")
        self.max_messages = configured_limit

    def create_session(self, title: str | None = None) -> ChatSession:
        now = datetime.now()
        session = ChatSession(
            external_id=str(uuid4()),
            title=(title or "").strip()[:80] or None,
            status=ChatSessionStatus.ACTIVE,
            message_count=0,
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, external_id: str) -> ChatSession | None:
        sessions = self.db.scalars(
            select(ChatSession).where(ChatSession.external_id == external_id)
        ).all()
        if not sessions:
            return None
        return sessions[0]

    def get_or_create_session(self, external_id: str) -> ChatSession:
        session = self.get_session(external_id)
        if session is not None:
            return session
        return self._create_session(external_id)

    def list_sessions(
        self,
        status: str | ChatSessionStatus | None = ChatSessionStatus.ACTIVE,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        if limit < 1 or offset < 0:
            raise ValueError("limit debe ser mayor que cero y offset no puede ser negativo.")
        status_value = status.value if isinstance(status, ChatSessionStatus) else status
        query = select(ChatSession)
        if status_value not in (None, "all"):
            query = query.where(ChatSession.status == status_value)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = self.db.scalars(
            query.order_by(ChatSession.last_message_at.desc(), ChatSession.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return items, total

    def append_message(
        self,
        session_external_id: str,
        role: str | ChatMessageRole,
        content: str,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_result: dict[str, Any] | None = None,
        agent_action_id: int | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
    ) -> ChatMessage:
        chat_session = self._locked_session(session_external_id)
        latest = self.db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.seq.desc())
            .limit(1)
            .with_for_update()
        ).all()
        seq = latest[0].seq + 1 if latest else 1
        now = datetime.now()
        chat_session.message_count = seq
        chat_session.last_message_at = now
        chat_session.updated_at = now
        normalized_role = ChatMessageRole(role)
        if normalized_role == ChatMessageRole.USER and not chat_session.title:
            prior_user_messages = self.db.scalars(
                select(ChatMessage.id)
                .where(
                    ChatMessage.session_id == chat_session.id,
                    ChatMessage.role == ChatMessageRole.USER,
                )
                .limit(1)
            ).all()
            if not prior_user_messages:
                chat_session.title = content.strip()[:80] or None

        message = ChatMessage(
            session_id=chat_session.id,
            seq=seq,
            role=normalized_role,
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
            tool_result=tool_result,
            agent_action_id=agent_action_id,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )
        self.db.add(message)
        self.db.flush()
        return message

    def get_history(
        self,
        session_external_id: str,
        limit: int | None = None,
        before_seq: int | None = None,
    ) -> list[ChatMessage]:
        chat_session = self._require_session(session_external_id)
        query = select(ChatMessage).where(ChatMessage.session_id == chat_session.id)
        if before_seq is not None:
            query = query.where(ChatMessage.seq < before_seq)
        if limit is None:
            return self.db.scalars(query.order_by(ChatMessage.seq.asc())).all()
        if limit < 0:
            raise ValueError("limit no puede ser negativo.")
        if limit == 0:
            return []
        latest = self.db.scalars(
            query.order_by(ChatMessage.seq.desc()).limit(limit)
        ).all()
        return list(reversed(latest))

    def get_llm_context(
        self,
        session_external_id: str,
        max_messages: int = 30,
    ) -> list[dict[str, Any]]:
        if max_messages < 1:
            raise ValueError("max_messages debe ser mayor que cero.")
        messages = self.get_history(session_external_id, limit=max_messages)
        while messages and messages[0].role == ChatMessageRole.TOOL:
            first_tool = messages[0]
            prior_assistants = self.db.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == first_tool.session_id,
                    ChatMessage.seq < first_tool.seq,
                    ChatMessage.role == ChatMessageRole.ASSISTANT,
                )
                .order_by(ChatMessage.seq.desc())
                .limit(max_messages)
            ).all()
            assistant = next(
                (
                    candidate
                    for candidate in prior_assistants
                    if candidate.tool_calls
                    and any(
                        call.get("id") == first_tool.tool_call_id
                        for call in candidate.tool_calls
                    )
                ),
                None,
            )
            if assistant is None:
                messages.pop(0)
                continue
            earlier_tool_results = self.db.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == first_tool.session_id,
                    ChatMessage.seq > assistant.seq,
                    ChatMessage.seq < first_tool.seq,
                    ChatMessage.role == ChatMessageRole.TOOL,
                )
                .order_by(ChatMessage.seq.asc())
            ).all()
            messages = [assistant, *earlier_tool_results, *messages]

        return [self._llm_message(item) for item in messages]

    def archive_session(self, external_id: str) -> ChatSession:
        session = self._require_session(external_id)
        session.status = ChatSessionStatus.ARCHIVED
        session.updated_at = datetime.now()
        self.db.flush()
        return session

    def rename_session(self, external_id: str, title: str) -> ChatSession:
        session = self._require_session(external_id)
        session.title = title.strip()[:80] or None
        session.updated_at = datetime.now()
        self.db.flush()
        return session

    def _create_session(self, external_id: str, title: str | None = None) -> ChatSession:
        now = datetime.now()
        session = ChatSession(
            external_id=external_id,
            title=(title or "").strip()[:80] or None,
            status=ChatSessionStatus.ACTIVE,
            message_count=0,
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def _locked_session(self, external_id: str) -> ChatSession:
        sessions = self.db.scalars(
            select(ChatSession)
            .where(ChatSession.external_id == external_id)
            .with_for_update()
        ).all()
        if sessions:
            return sessions[0]
        raise SessionNotFoundError(external_id)

    def _require_session(self, external_id: str) -> ChatSession:
        session = self.get_session(external_id)
        if session is None:
            raise SessionNotFoundError(external_id)
        return session

    @staticmethod
    def _llm_message(message: ChatMessage) -> dict[str, Any]:
        result: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.tool_name:
            result["name"] = message.tool_name
        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            result["tool_calls"] = message.tool_calls
        return result
