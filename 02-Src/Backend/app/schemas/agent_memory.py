from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.enums import AgentMemoryFactStatus
from app.schemas.common import Schema


class AgentMemoryFactOut(Schema):
    id: int
    key: str
    value: str
    source_session_id: int
    source_message_id: int | None
    status: AgentMemoryFactStatus
    created_at: datetime
    updated_at: datetime


class AgentMemoryFactPatch(Schema):
    status: Literal["disabled"] = Field(
        description="Deshabilita el dato sin eliminarlo.",
        examples=["disabled"],
    )
