from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, ProductDTO, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("", response_model=APIEnvelope[list[ProductDTO]], responses=responses(422, 500))
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    query: str | None = None,
    supplier_id: int | None = Query(default=None, gt=0),
    category: str | None = None,
    sort: str = "id",
    db: Session = Depends(get_db),
):
    data, meta = service.list_products(db, page, per_page, query, supplier_id, category, sort)
    return {"data": data, "meta": meta}


@router.get("/{product_id}", response_model=APIEnvelope[ProductDTO], responses=responses(404, 500))
def get_product(product_id: int, db: Session = Depends(get_db)):
    return {"data": service.get_product(db, product_id), "meta": {}}
