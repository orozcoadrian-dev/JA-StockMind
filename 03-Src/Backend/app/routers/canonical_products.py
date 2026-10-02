from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, CanonicalDTO, CanonicalPatch, CanonicalRequest, ProductDTO, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/canonical-products", tags=["Catálogo"])


@router.get("", response_model=APIEnvelope[list[CanonicalDTO]], responses=responses(422, 500))
def list_canonical_products(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), category: str | None = None, db: Session = Depends(get_db)):
    data, meta = service.list_canonical_products(db, page, per_page, category)
    return {"data": data, "meta": meta}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIEnvelope[CanonicalDTO], responses=responses(400, 422, 500))
def create_canonical_product(payload: CanonicalRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    data = service.create_canonical_product(db, payload.model_dump())
    response.headers["Location"] = str(request.url_for("get_canonical_product", canonical_id=data["id"]))
    return {"data": data, "meta": {}}


@router.get("/{canonical_id}", name="get_canonical_product", response_model=APIEnvelope[CanonicalDTO], responses=responses(404, 500))
def get_canonical_product(canonical_id: int, db: Session = Depends(get_db)):
    return {"data": service.get_canonical_product(db, canonical_id), "meta": {}}


@router.patch("/{canonical_id}", response_model=APIEnvelope[CanonicalDTO], responses=responses(400, 404, 422, 500))
def patch_canonical_product(canonical_id: int, payload: CanonicalPatch, db: Session = Depends(get_db)):
    data = service.update_canonical_product(db, canonical_id, payload.model_dump(exclude_unset=True))
    return {"data": data, "meta": {}}


@router.get("/{canonical_id}/suppliers", response_model=APIEnvelope[list[ProductDTO]], responses=responses(404, 500))
def canonical_suppliers(canonical_id: int, db: Session = Depends(get_db)):
    data = service.canonical_suppliers(db, canonical_id)
    return {"data": data, "meta": {"total": len(data)}}
