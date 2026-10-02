from datetime import datetime
from typing import Any

from app.schemas.common import Schema


class AgentActionCreate(Schema):
    session_id: str | None = None
    tool: str
    input_params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    required_confirmation: bool = False
    approved: bool | None = None


class AgentActionUpdate(Schema):
    result: dict[str, Any] | None = None
    required_confirmation: bool | None = None
    approved: bool | None = None


class AgentActionRead(AgentActionCreate):
    id: int
    created_at: datetime