from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Backend.Agent.persistent_memory import MemoryFactNotFoundError, PersistentMemory
from Backend.Services.api_v1 import APIServiceError
from ..db.session import get_db
from ..schemas.agent_memory import AgentMemoryFactOut, AgentMemoryFactPatch
from ..schemas.api import APIEnvelope, responses


router = APIRouter(prefix="/agent/memory", tags=["Memoria del agente"])
ERROR_DOCS = responses(404, 422, 500)


@router.get(
    "/facts",
    response_model=APIEnvelope[list[AgentMemoryFactOut]],
    responses={
        **ERROR_DOCS,
        200: {
            "description": "Facts de memoria paginados",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": 8,
                                "key": "supplier_preference",
                                "value": "Comparar precios por proveedor Malusa primero.",
                                "source_session_id": 12,
                                "source_message_id": 31,
                                "status": "active",
                                "created_at": "2026-11-19T10:01:00",
                                "updated_at": "2026-11-19T10:01:00",
                            }
                        ],
                        "meta": {"total": 1, "limit": 20, "offset": 0},
                    }
                }
            },
        },
    },
)
def list_agent_memory_facts(
    status_filter: Literal["active", "disabled", "all"] = Query(
        default="active",
        alias="status",
        description="Filtra por estado; all incluye facts activos y deshabilitados.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    status_value = None if status_filter == "all" else status_filter
    facts, total = PersistentMemory(db).list_memory_facts(
        status=status_value,
        limit=limit,
        offset=offset,
    )
    return {"data": facts, "meta": {"total": total, "limit": limit, "offset": offset}}


@router.patch(
    "/facts/{fact_id}",
    response_model=APIEnvelope[AgentMemoryFactOut],
    responses={**ERROR_DOCS, 200: {"description": "Fact deshabilitado sin borrar su registro"}},
)
def disable_agent_memory_fact(
    fact_id: int,
    payload: AgentMemoryFactPatch,
    db: Session = Depends(get_db),
):
    if payload.status != "disabled":
        raise APIServiceError(422, "Los facts de memoria solo pueden deshabilitarse.")
    try:
        fact = PersistentMemory(db).disable_memory_fact(fact_id)
    except MemoryFactNotFoundError as exc:
        raise APIServiceError(404, str(exc)) from exc
    db.commit()
    db.refresh(fact)
    return {"data": fact, "meta": {}}
