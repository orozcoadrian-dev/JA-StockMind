from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, RuleDTO, RulePatch, RuleRequest, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/rules", tags=["Reglas"])


@router.get("", response_model=APIEnvelope[list[RuleDTO]], responses=responses(422, 500))
def list_rules(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    data, meta = service.list_rules(db, page, per_page)
    return {"data": data, "meta": meta}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIEnvelope[RuleDTO], responses=responses(409, 422, 500))
def create_rule(payload: RuleRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    data = service.create_rule(db, payload.model_dump(exclude_none=True))
    response.headers["Location"] = str(request.url_for("get_rule", rule_id=data["id"]))
    return {"data": data, "meta": {}}


@router.get("/{rule_id}", name="get_rule", response_model=APIEnvelope[RuleDTO], responses=responses(404, 500))
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    return {"data": service.get_rule(db, rule_id), "meta": {}}


@router.patch("/{rule_id}", response_model=APIEnvelope[RuleDTO], responses=responses(404, 409, 422, 500))
def patch_rule(rule_id: int, payload: RulePatch, db: Session = Depends(get_db)):
    data = service.update_rule(db, rule_id, payload.model_dump(exclude_unset=True, exclude_none=True))
    return {"data": data, "meta": {}}


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, responses=responses(404, 500))
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    service.delete_rule(db, rule_id)
