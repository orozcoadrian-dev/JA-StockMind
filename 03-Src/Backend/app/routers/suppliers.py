from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..schemas.api import APIEnvelope, SupplierDTO, SupplierPatch, SupplierRequest, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/suppliers", tags=["Proveedores"])


@router.get("", response_model=APIEnvelope[list[SupplierDTO]], responses=responses(500))
def list_suppliers(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    data, meta = service.list_suppliers(db, page, per_page)
    return {"data": data, "meta": meta}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIEnvelope[SupplierDTO], responses=responses(409, 422, 500))
def create_supplier(payload: SupplierRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    data = service.create_supplier(db, payload.model_dump())
    response.headers["Location"] = str(request.url_for("get_supplier", supplier_id=data["id"]))
    return {"data": data, "meta": {}}


@router.get("/{supplier_id}", name="get_supplier", response_model=APIEnvelope[SupplierDTO], responses=responses(404, 500))
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    return {"data": service.get_supplier(db, supplier_id), "meta": {}}


@router.patch("/{supplier_id}", response_model=APIEnvelope[SupplierDTO], responses=responses(404, 409, 422, 500))
def patch_supplier(supplier_id: int, payload: SupplierPatch, db: Session = Depends(get_db)):
    data = service.update_supplier(db, supplier_id, payload.model_dump(exclude_unset=True))
    return {"data": data, "meta": {}}


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, responses=responses(404, 409, 500))
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    service.delete_supplier(db, supplier_id)
