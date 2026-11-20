from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, ProductDTO, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/reports", tags=["Reportes"])


@router.get("/inventory", response_model=APIEnvelope[dict], responses=responses(422, 500))
def inventory_report(category: str | None = None, db: Session = Depends(get_db)):
    return {"data": service.inventory_report(db, category), "meta": {}}


@router.get("/price-comparison", response_model=APIEnvelope[list[ProductDTO]], responses=responses(404, 422, 500))
def price_comparison(canonical_product_id: int = Query(gt=0), db: Session = Depends(get_db)):
    data = service.price_comparison(db, canonical_product_id)
    return {"data": data, "meta": {"total": len(data)}}


@router.get("/purchase-suggestions", response_model=APIEnvelope[list[dict]], responses=responses(422, 500))
def purchase_suggestions(budget: Decimal | None = Query(default=None, ge=0), categories: list[str] | None = Query(default=None), db: Session = Depends(get_db)):
    data = service.purchase_suggestions(db, budget, categories)
    return {"data": data, "meta": {"total": len(data)}}
