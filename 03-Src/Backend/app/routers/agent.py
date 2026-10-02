from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..core.rate_limit import limiter
from ..db.session import get_db
from ..schemas.api import APIEnvelope, AgentChatRequest, AgentConfirmRequest, responses
from Backend.Agent.core import agent_core
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/agent", tags=["Agente"])


@router.post("/chat", response_model=APIEnvelope[dict], responses=responses(422, 429, 500, 503))
@limiter.limit("30/minute")
def agent_chat(request: Request, payload: AgentChatRequest):
    return {"data": agent_core.run(payload.message, payload.session_id), "meta": {}}


@router.post("/confirm", response_model=APIEnvelope[dict], responses=responses(404, 409, 422, 500))
def agent_confirm(payload: AgentConfirmRequest):
    try:
        result = agent_core.confirm_action(payload.action_id, payload.approved)
    except ValueError as exc:
        from Backend.Services.api_v1 import APIServiceError

        raise APIServiceError(404, str(exc)) from exc
    return {"data": result, "meta": {}}


@router.get("/actions", response_model=APIEnvelope[list[dict]], responses=responses(422, 500))
def agent_actions(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    data, meta = service.list_agent_actions(db, page, per_page)
    return {"data": data, "meta": meta}
