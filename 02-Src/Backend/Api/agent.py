from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from Backend.Agent.core import AgentCore
from Backend.Models.agent_action import AgentAction
from Backend.database import SessionLocal

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_core = AgentCore()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="default", min_length=1, max_length=100)


class ConfirmRequest(BaseModel):
    action_id: int = Field(gt=0)
    approved: bool


@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        return {"data": agent_core.run(payload.message, payload.session_id), "meta": {}}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/confirm")
def confirm(payload: ConfirmRequest):
    try:
        return {"data": agent_core.confirm_action(payload.action_id, payload.approved), "meta": {}}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/actions")
def actions():
    db = SessionLocal()
    try:
        records = db.scalars(select(AgentAction).order_by(AgentAction.timestamp.desc()).limit(100)).all()
        return {"data": [{"id": record.id, "timestamp": record.timestamp.isoformat(), "tool_name": record.tool_name, "input_payload": record.input_payload, "result": record.result, "required_confirmation": record.required_confirmation, "approved": record.approved} for record in records], "meta": {"total": len(records)}}
    finally:
        db.close()