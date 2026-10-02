from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, MatchDTO, MatchRejectRequest, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/matches", tags=["Coincidencias"])


@router.get("/pending", response_model=APIEnvelope[list[MatchDTO]], responses=responses(422, 500))
def pending_matches(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    data, meta = service.list_pending_matches(db, page, per_page)
    return {"data": data, "meta": meta}


@router.post("/suggest", response_model=APIEnvelope[list[dict]], responses=responses(500))
def suggest_matches(db: Session = Depends(get_db)):
    data = service.suggest_matches(db)
    return {"data": data, "meta": {"total": len(data)}}


@router.post("/{suggestion_id}/confirm", response_model=APIEnvelope[dict], responses=responses(404, 409, 500))
def confirm_match(suggestion_id: int, db: Session = Depends(get_db)):
    return {"data": service.confirm_match(db, suggestion_id), "meta": {}}


@router.post("/{suggestion_id}/reject", response_model=APIEnvelope[dict], responses=responses(404, 409, 500))
def reject_match(suggestion_id: int, payload: MatchRejectRequest | None = None, db: Session = Depends(get_db)):
    return {"data": service.reject_match(db, suggestion_id, payload.model_dump() if payload else None), "meta": {}}
