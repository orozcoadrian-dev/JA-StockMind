from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.Agent.persistent_memory import PersistentMemory, SessionNotFoundError
from ..core.rate_limit import limiter
from ..db.session import get_db
from ..models import ChatMessage, ChatMessageRole, ChatSessionStatus
from ..schemas.api import APIEnvelope, responses
from ..schemas.chat import ChatMessageOut, ChatSessionCreate, ChatSessionOut, ChatSessionUpdate


router = APIRouter(prefix="/agent/sessions", tags=["Sesiones del agente"])
SESSION_RESPONSE_EXAMPLE = {
    "data": {
        "id": 12,
        "external_id": "d2719b7e-7d7a-48a6-a012-31fae2d4d000",
        "title": "Consulta de inventario",
        "status": "active",
        "created_at": "2026-11-19T10:00:00",
        "updated_at": "2026-11-19T10:05:00",
        "last_message_at": "2026-11-19T10:05:00",
        "message_count": 2,
    },
    "meta": {},
}
ERROR_DOCS = responses(404, 422, 429, 500)


def _session_or_404(db: Session, session_id: UUID4):
    session = PersistentMemory(db).get_session(str(session_id))
    if session is None:
        raise SessionNotFoundError(str(session_id))
    return session


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=APIEnvelope[ChatSessionOut],
    responses={
        **ERROR_DOCS,
        201: {
            "description": "Sesión creada",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
    },
)
@limiter.limit("30/minute")
def create_agent_session(request: Request, payload: ChatSessionCreate, db: Session = Depends(get_db)):
    memory = PersistentMemory(db)
    session = memory.create_session(payload.title)
    db.commit()
    db.refresh(session)
    return {"data": session, "meta": {}}


@router.get(
    "",
    response_model=APIEnvelope[list[ChatSessionOut]],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Sesiones paginadas",
            "content": {
                "application/json": {
                    "example": {
                        "data": [SESSION_RESPONSE_EXAMPLE["data"]],
                        "meta": {"total": 1, "limit": 20, "offset": 0},
                    }
                }
            },
        },
    },
)
def list_agent_sessions(
    status_filter: Literal["active", "archived", "all"] = Query(
        default="active",
        alias="status",
        description="Filtra por estado; all incluye sesiones activas y archivadas.",
        examples=["active", "archived", "all"],
    ),
    limit: int = Query(default=20, ge=1, le=100, examples=[20]),
    offset: int = Query(default=0, ge=0, examples=[0]),
    db: Session = Depends(get_db),
):
    session_status = None if status_filter == "all" else ChatSessionStatus(status_filter)
    items, total = PersistentMemory(db).list_sessions(session_status, limit, offset)
    return {"data": items, "meta": {"total": total, "limit": limit, "offset": offset}}


@router.get(
    "/{session_id}",
    response_model=APIEnvelope[ChatSessionOut],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Detalle de sesión",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
    },
)
def get_agent_session(session_id: UUID4, db: Session = Depends(get_db)):
    return {"data": _session_or_404(db, session_id), "meta": {}}


@router.get(
    "/{session_id}/messages",
    response_model=APIEnvelope[list[ChatMessageOut]],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Mensajes ordenados por seq",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": 31,
                                "session_id": 12,
                                "seq": 1,
                                "role": "user",
                                "content": "¿Qué productos tienen poco stock?",
                                "tool_name": None,
                                "tool_call_id": None,
                                "tool_calls": None,
                                "tool_result": None,
                                "agent_action_id": None,
                                "model": None,
                                "tokens_input": None,
                                "tokens_output": None,
                                "created_at": "2026-11-19T10:01:00",
                            }
                        ],
                        "meta": {"limit": 50, "before_seq": None},
                    }
                }
            },
        },
    },
)
def list_agent_session_messages(
    session_id: UUID4,
    limit: int = Query(default=50, ge=1, le=500, examples=[50]),
    before_seq: int | None = Query(default=None, ge=1, examples=[31]),
    include_tools: bool = Query(default=False, examples=[False, True]),
    db: Session = Depends(get_db),
):
    session = _session_or_404(db, session_id)
    query = select(ChatMessage).where(ChatMessage.session_id == session.id)
    if before_seq is not None:
        query = query.where(ChatMessage.seq < before_seq)
    if not include_tools:
        query = query.where(ChatMessage.role.in_([ChatMessageRole.USER, ChatMessageRole.ASSISTANT]))
    messages = list(
        reversed(db.scalars(query.order_by(ChatMessage.seq.desc()).limit(limit)).all())
    )
    return {
        "data": messages,
        "meta": {"limit": limit, "before_seq": before_seq, "include_tools": include_tools},
    }


@router.patch(
    "/{session_id}",
    response_model=APIEnvelope[ChatSessionOut],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Sesión actualizada; status archived la archiva y active la reactiva",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
    },
)
@limiter.limit("30/minute")
def update_agent_session(
    request: Request,
    session_id: UUID4,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
):
    memory = PersistentMemory(db)
    session = _session_or_404(db, session_id)
    if "title" in payload.model_fields_set:
        memory.rename_session(str(session_id), payload.title or "")
    if payload.status is not None:
        if payload.status == ChatSessionStatus.ARCHIVED:
            memory.archive_session(str(session_id))
        else:
            session.status = ChatSessionStatus.ACTIVE
            session.updated_at = datetime.now()
    db.commit()
    db.refresh(session)
    return {"data": session, "meta": {}}


@router.get(
    "/{session_id}/export",
    response_model=APIEnvelope[dict[str, Any]],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Conversación completa, incluidas llamadas y resultados de herramientas",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "session": SESSION_RESPONSE_EXAMPLE["data"],
                            "messages": [
                                {
                                    "id": 32,
                                    "session_id": 12,
                                    "seq": 2,
                                    "role": "assistant",
                                    "content": "",
                                    "tool_name": None,
                                    "tool_call_id": None,
                                    "tool_calls": [
                                        {
                                            "id": "call-search",
                                            "type": "function",
                                            "function": {
                                                "name": "search_products",
                                                "arguments": "{\"query\":\"grip rojo\"}",
                                            },
                                        }
                                    ],
                                    "tool_result": None,
                                    "agent_action_id": None,
                                    "model": "gemini",
                                    "tokens_input": 42,
                                    "tokens_output": 8,
                                    "created_at": "2026-11-19T10:01:00",
                                },
                                {
                                    "id": 33,
                                    "session_id": 12,
                                    "seq": 3,
                                    "role": "tool",
                                    "content": "{\"data\":[]}",
                                    "tool_name": "search_products",
                                    "tool_call_id": "call-search",
                                    "tool_calls": None,
                                    "tool_result": {"data": []},
                                    "agent_action_id": None,
                                    "model": None,
                                    "tokens_input": None,
                                    "tokens_output": None,
                                    "created_at": "2026-11-19T10:01:01",
                                },
                            ],
                        },
                        "meta": {"message_count": 4},
                    }
                }
            },
        },
    },
)
def export_agent_session(session_id: UUID4, db: Session = Depends(get_db)):
    session = _session_or_404(db, session_id)
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.seq.asc())
    ).all()
    return {
        "data": {
            "session": ChatSessionOut.model_validate(session).model_dump(mode="json"),
            "messages": [ChatMessageOut.model_validate(message).model_dump(mode="json") for message in messages],
        },
        "meta": {"message_count": len(messages)},
    }
