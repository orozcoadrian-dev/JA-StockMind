from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.models.enums import ChatMessageRole, ChatSessionStatus
from app.schemas.common import Schema


class ChatSessionCreate(Schema):
    title: str | None = Field(default=None, max_length=80)

    model_config = {
        **Schema.model_config,
        "json_schema_extra": {"examples": [{"title": "Consulta de inventario"}]},
    }


class ChatSessionUpdate(Schema):
    title: str | None = Field(default=None, max_length=80)
    status: ChatSessionStatus | None = None

    model_config = {
        **Schema.model_config,
        "json_schema_extra": {
            "examples": [
                {"title": "Inventario de frenos"},
                {"status": "archived"},
                {"status": "active"},
            ]
        },
    }

    @model_validator(mode="after")
    def require_update(self):
        if self.title is None and self.status is None:
            raise ValueError("Debes indicar title o status para actualizar la sesión.")
        return self


class ChatSessionOut(Schema):
    id: int
    external_id: str
    title: str | None
    status: ChatSessionStatus
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    message_count: int


class ChatMessageOut(Schema):
    id: int
    session_id: int
    seq: int
    role: ChatMessageRole
    content: str
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_result: dict[str, Any] | None = None
    agent_action_id: int | None = None
    model: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    created_at: datetime
