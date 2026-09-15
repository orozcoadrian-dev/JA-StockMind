from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from Backend.Agent.core import agent_core
from Backend.Agent.tools import _canonical_data, execute_tool
from Backend.Models.agent_action import AgentAction
from Backend.Models.canonical_product import CanonicalProduct
from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.import_record import ImportRecord
from Backend.Models.match_suggestion import MatchSuggestion
from Backend.Models.product import Product
from Backend.Models.product_link import ProductLink
from Backend.Models.schemas import CanonicalProductCreate, EquivalenceRuleCreate, SupplierCreate
from Backend.Models.supplier import Supplier
from Backend.Services.consolidator import consolidate_products
from Backend.Services.importer import _save_uploaded_file, import_excel_file
from Backend.config import BaseConfig
from Backend.database import SessionLocal

router = APIRouter(prefix="/api/v1", tags=["api-v1"])
_rate_state: dict[str, list[float]] = {}


class ProductFilters(BaseModel):
    query: str | None = None
    supplier_id: int | None = Field(default=None, gt=0)
    category: str | None = None
    sort: str = "id"


class RulePatch(BaseModel):
    active: bool | None = None
    structured_condition: dict[str, Any] | None = None


class SupplierPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    nit: str | None = Field(default=None, min_length=5, max_length=50)
    contact: str | None = Field(default=None, max_length=200)
    active: bool | None = None


class CanonicalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=300)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    attributes: dict[str, Any] | None = None
    stock_in_bodega: int | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)


class ProductIdsRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2)
    canonical_name: str | None = None


class MatchRejectRequest(BaseModel):
    create_exclusion_rule: bool = False
    original_text: str | None = Field(default=None, max_length=500)


class AgentConfirmRequest(BaseModel):
    action_id: int = Field(gt=0)
    approved: bool


def rate_limit(request: Request):
    key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
    now = time.monotonic()
    recent = [stamp for stamp in _rate_state.get(key, []) if now - stamp < 60]
    if len(recent) >= 30:
        raise HTTPException(status_code=429, detail="Límite temporal de solicitudes excedido.")
    recent.append(now)
    _rate_state[key] = recent


def page_params(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)) -> tuple[int, int]:
    return page, per_page


def paged(query, db, page: int, per_page: int):
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    return rows, {"page": page, "per_page": per_page, "total": total, "pages": math.ceil(total / per_page) if total else 0}


def supplier_data(item: Supplier) -> dict:
    return {"id": item.id, "name": item.name, "nit": item.nit, "contact": item.contact, "active": item.active, "created_at": item.created_at.isoformat()}


def product_data(item: Product) -> dict:
    return {"id": item.id, "supplier_id": item.supplier_id, "provider_code": item.provider_code, "raw_name": item.raw_name, "normalized_name": item.normalized_name, "category": item.category, "unit_price": float(item.unit_price), "currency": item.currency, "unit_of_measure": item.unit_of_measure, "pack_quantity": item.pack_quantity, "price_list_date": item.price_list_date.isoformat(), "row_hash": item.row_hash}


def rule_data(item: EquivalenceRule) -> dict:
    return {"id": item.id, "original_text": item.original_text, "structured_condition": item.structured_condition, "supplier_names": item.supplier_names, "active": item.active, "created_at": item.created_at.isoformat(), "applied_count": item.applied_count}


@router.get("/health", tags=["health"])
def api_health():
    db = SessionLocal()
    try:
        db.execute(select(1))
        return {"data": {"status": "ok", "version": "v1", "database": "ok"}, "meta": {}}
    finally:
        db.close()


@router.get("/suppliers")
def list_suppliers(page_params_value: tuple[int, int] = Depends(page_params)):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        rows, meta = paged(select(Supplier).order_by(Supplier.id), db, page, per_page)
        return {"data": [supplier_data(row) for row in rows], "meta": meta}
    finally:
        db.close()


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, request: Request):
    db = SessionLocal()
    try:
        item = Supplier(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return JSONResponse(status_code=201, headers={"Location": str(request.url_for("get_supplier", supplier_id=item.id))}, content={"data": supplier_data(item), "meta": {}})
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El proveedor o NIT ya existe.")
    finally:
        db.close()


@router.get("/suppliers/{supplier_id}", name="get_supplier")
def get_supplier(supplier_id: int):
    db = SessionLocal()
    try:
        item = db.get(Supplier, supplier_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El proveedor no existe.")
        return {"data": supplier_data(item), "meta": {}}
    finally:
        db.close()


@router.patch("/suppliers/{supplier_id}")
def patch_supplier(supplier_id: int, payload: SupplierPatch):
    db = SessionLocal()
    try:
        item = db.get(Supplier, supplier_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El proveedor no existe.")
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(item, key, value)
        db.commit()
        return {"data": supplier_data(item), "meta": {}}
    finally:
        db.close()


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int):
    db = SessionLocal()
    try:
        item = db.get(Supplier, supplier_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El proveedor no existe.")
        if db.scalar(select(Product.id).where(Product.supplier_id == supplier_id).limit(1)):
            raise HTTPException(status_code=409, detail="No se puede borrar un proveedor con productos.")
        db.delete(item)
        db.commit()
    finally:
        db.close()


@router.post("/imports", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def create_import(request: Request, file: UploadFile = File(...), supplier_id: int = Form(...)):
    if request.headers.get("content-length") and int(request.headers["content-length"]) > BaseConfig.MAX_CONTENT_LENGTH:
        raise HTTPException(status_code=413, detail="El archivo excede el tamaño máximo permitido.")
    db = SessionLocal()
    try:
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="El proveedor no existe.")
        filename = file.filename or "upload.xlsx"
        if filename.lower().rsplit(".", 1)[-1] not in {"xlsx", "xls", "csv"}:
            raise HTTPException(status_code=422, detail="La extensión del archivo no es válida.")
        stored = _save_uploaded_file(file.file, filename)
        summary = import_excel_file(stored, supplier_id)
        record = ImportRecord(supplier_id=supplier_id, filename=filename, stored_file_path=stored, summary=summary)
        db.add(record)
        db.commit()
        db.refresh(record)
        return {"data": {"id": record.id, "filename": filename, "supplier_id": supplier_id, "summary": summary}, "meta": {}}
    finally:
        db.close()


@router.get("/imports")
def list_imports(page_params_value: tuple[int, int] = Depends(page_params), supplier_id: int | None = None):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        query = select(ImportRecord).order_by(ImportRecord.created_at.desc())
        if supplier_id:
            query = query.where(ImportRecord.supplier_id == supplier_id)
        rows, meta = paged(query, db, page, per_page)
        return {"data": [{"id": row.id, "supplier_id": row.supplier_id, "filename": row.filename, "stored_file_path": row.stored_file_path, "summary": row.summary, "created_at": row.created_at.isoformat()} for row in rows], "meta": meta}
    finally:
        db.close()


@router.get("/imports/{import_id}")
def get_import(import_id: int):
    db = SessionLocal()
    try:
        row = db.get(ImportRecord, import_id)
        if row is None:
            raise HTTPException(status_code=404, detail="La importación no existe.")
        return {"data": {"id": row.id, "supplier_id": row.supplier_id, "filename": row.filename, "stored_file_path": row.stored_file_path, "summary": row.summary, "created_at": row.created_at.isoformat()}, "meta": {}}
    finally:
        db.close()


@router.get("/products")
def list_products(page_params_value: tuple[int, int] = Depends(page_params), query: str | None = None, supplier_id: int | None = None, category: str | None = None, sort: str = "id"):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        columns = {"id": Product.id, "price": Product.unit_price, "name": Product.normalized_name, "category": Product.category}
        order_column = columns.get(sort.lstrip("-"), Product.id)
        query_statement = select(Product)
        if query:
            query_statement = query_statement.where(or_(Product.normalized_name.ilike(f"%{query}%"), Product.raw_name.ilike(f"%{query}%")))
        if supplier_id:
            query_statement = query_statement.where(Product.supplier_id == supplier_id)
        if category:
            query_statement = query_statement.where(Product.category == category)
        query_statement = query_statement.order_by(order_column.desc() if sort.startswith("-") else order_column)
        rows, meta = paged(query_statement, db, page, per_page)
        return {"data": [product_data(row) for row in rows], "meta": meta}
    finally:
        db.close()


@router.get("/products/{product_id}")
def get_product(product_id: int):
    db = SessionLocal()
    try:
        item = db.get(Product, product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El producto no existe.")
        return {"data": product_data(item), "meta": {}}
    finally:
        db.close()


@router.get("/canonical-products")
def list_canonical(page_params_value: tuple[int, int] = Depends(page_params), category: str | None = None):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        query = select(CanonicalProduct).order_by(CanonicalProduct.id)
        if category:
            query = query.where(CanonicalProduct.category == category)
        rows, meta = paged(query, db, page, per_page)
        return {"data": [_canonical_data(row, db) for row in rows], "meta": meta}
    finally:
        db.close()


@router.post("/canonical-products", status_code=status.HTTP_201_CREATED)
def create_canonical(payload: CanonicalProductCreate, request: Request):
    db = SessionLocal()
    try:
        item = CanonicalProduct(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return JSONResponse(status_code=201, headers={"Location": str(request.url_for("get_canonical", canonical_id=item.id))}, content={"data": _canonical_data(item, db), "meta": {}})
    finally:
        db.close()


@router.get("/canonical-products/{canonical_id}", name="get_canonical")
def get_canonical(canonical_id: int):
    db = SessionLocal()
    try:
        item = db.get(CanonicalProduct, canonical_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El producto canónico no existe.")
        return {"data": _canonical_data(item, db), "meta": {}}
    finally:
        db.close()


@router.patch("/canonical-products/{canonical_id}")
def patch_canonical(canonical_id: int, payload: CanonicalPatch):
    db = SessionLocal()
    try:
        item = db.get(CanonicalProduct, canonical_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El producto canónico no existe.")
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(item, key, value)
        db.commit()
        return {"data": _canonical_data(item, db), "meta": {}}
    finally:
        db.close()


@router.get("/canonical-products/{canonical_id}/suppliers")
def canonical_suppliers(canonical_id: int):
    db = SessionLocal()
    try:
        item = db.get(CanonicalProduct, canonical_id)
        if item is None:
            raise HTTPException(status_code=404, detail="El producto canónico no existe.")
        return {"data": _canonical_data(item, db)["suppliers"], "meta": {"total": len(_canonical_data(item, db)["suppliers"])} }
    finally:
        db.close()


@router.post("/matches/suggest")
def suggest_matches():
    result = execute_tool("suggest_matches", {}, db=None)
    return {"data": result.get("data", []), "meta": {"summary": result.get("summary")}}


def suggestion_data(row: MatchSuggestion, db) -> dict:
    return {"id": row.id, "product": product_data(db.get(Product, row.product_id)), "candidate": product_data(db.get(Product, row.candidate_product_id)), "score": row.score, "reasons": row.reasons, "decision": row.decision, "status": row.status}


@router.get("/matches/pending")
def pending_matches(page_params_value: tuple[int, int] = Depends(page_params)):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        rows, meta = paged(select(MatchSuggestion).where(MatchSuggestion.status == "pending").order_by(MatchSuggestion.score.desc()), db, page, per_page)
        return {"data": [suggestion_data(row, db) for row in rows], "meta": meta}
    finally:
        db.close()


@router.post("/matches/{suggestion_id}/confirm")
def confirm_match(suggestion_id: int):
    db = SessionLocal()
    try:
        row = db.get(MatchSuggestion, suggestion_id)
        if row is None:
            raise HTTPException(status_code=404, detail="La sugerencia no existe.")
        if row.status != "pending":
            raise HTTPException(status_code=409, detail="La sugerencia ya fue resuelta.")
        products = [db.get(Product, row.product_id), db.get(Product, row.candidate_product_id)]
        canonical = consolidate_products(db, products, row.score, origin="manual_confirmation", confirmed_by="user")
        row.status = "confirmed"
        row.resolved_at = datetime.utcnow()
        db.commit()
        return {"data": {"suggestion": suggestion_data(row, db), "canonical_product": _canonical_data(canonical, db)}, "meta": {}}
    finally:
        db.close()


@router.post("/matches/{suggestion_id}/reject")
def reject_match(suggestion_id: int, payload: MatchRejectRequest | None = None):
    db = SessionLocal()
    try:
        row = db.get(MatchSuggestion, suggestion_id)
        if row is None:
            raise HTTPException(status_code=404, detail="La sugerencia no existe.")
        if row.status != "pending":
            raise HTTPException(status_code=409, detail="La sugerencia ya fue resuelta.")
        row.status = "rejected"
        row.resolved_at = datetime.utcnow()
        if payload and payload.create_exclusion_rule:
            left, right = db.get(Product, row.product_id), db.get(Product, row.candidate_product_id)
            db.add(EquivalenceRule(original_text=payload.original_text or f"No fusionar {left.raw_name} con {right.raw_name}", structured_condition={"type": "exclusion", "match": {"keywords": list(set(left.normalized_name.split()) & set(right.normalized_name.split()))}, "suppliers": [], "action": "block_merge", "confidence": 1.0}, supplier_names=[], active=True))
        db.commit()
        return {"data": suggestion_data(row, db), "meta": {}}
    finally:
        db.close()


@router.get("/rules")
def list_rules(page_params_value: tuple[int, int] = Depends(page_params)):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        rows, meta = paged(select(EquivalenceRule).order_by(EquivalenceRule.id.desc()), db, page, per_page)
        return {"data": [rule_data(row) for row in rows], "meta": meta}
    finally:
        db.close()


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(payload: EquivalenceRuleCreate, request: Request):
    db = SessionLocal()
    try:
        item = EquivalenceRule(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return JSONResponse(status_code=201, headers={"Location": str(request.url_for("get_rule", rule_id=item.id))}, content={"data": rule_data(item), "meta": {}})
    finally:
        db.close()


@router.get("/rules/{rule_id}", name="get_rule")
def get_rule(rule_id: int):
    db = SessionLocal()
    try:
        item = db.get(EquivalenceRule, rule_id)
        if item is None:
            raise HTTPException(status_code=404, detail="La regla no existe.")
        return {"data": rule_data(item), "meta": {}}
    finally:
        db.close()


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, payload: RulePatch):
    db = SessionLocal()
    try:
        item = db.get(EquivalenceRule, rule_id)
        if item is None:
            raise HTTPException(status_code=404, detail="La regla no existe.")
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(item, key, value)
        db.commit()
        return {"data": rule_data(item), "meta": {}}
    finally:
        db.close()


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int):
    db = SessionLocal()
    try:
        item = db.get(EquivalenceRule, rule_id)
        if item is None:
            raise HTTPException(status_code=404, detail="La regla no existe.")
        db.delete(item)
        db.commit()
    finally:
        db.close()


@router.post("/agent/chat", dependencies=[Depends(rate_limit)])
def agent_chat(payload: dict):
    if not isinstance(payload.get("message"), str) or not payload["message"].strip():
        raise HTTPException(status_code=422, detail="message es obligatorio.")
    return {"data": agent_core.run(payload["message"], payload.get("session_id", "default")), "meta": {}}


@router.post("/agent/confirm")
def agent_confirm(payload: AgentConfirmRequest):
    try:
        return {"data": agent_core.confirm_action(payload.action_id, payload.approved), "meta": {}}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/agent/actions")
def agent_actions(page_params_value: tuple[int, int] = Depends(page_params)):
    page, per_page = page_params_value
    db = SessionLocal()
    try:
        rows, meta = paged(select(AgentAction).order_by(AgentAction.timestamp.desc()), db, page, per_page)
        return {"data": [{"id": row.id, "timestamp": row.timestamp.isoformat(), "tool_name": row.tool_name, "input_payload": row.input_payload, "result": row.result, "required_confirmation": row.required_confirmation, "approved": row.approved} for row in rows], "meta": meta}
    finally:
        db.close()


@router.get("/reports/inventory")
def inventory_report(category: str | None = None):
    result = execute_tool("get_inventory_report", {"filters": {"category": category} if category else {}}, db=None)
    return {"data": result.get("data", {}), "meta": {"summary": result.get("summary")}}


@router.get("/reports/price-comparison")
def price_comparison(canonical_product_id: int = Query(..., gt=0)):
    result = execute_tool("compare_supplier_prices", {"id": canonical_product_id}, db=None)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return {"data": result.get("data", []), "meta": {"summary": result.get("summary")}}


@router.get("/reports/purchase-suggestions")
def purchase_suggestions(budget: float | None = Query(default=None, ge=0), categories: list[str] | None = Query(default=None)):
    result = execute_tool("get_purchase_suggestions", {"budget": budget, "categories": categories}, db=None)
    return {"data": result.get("data", []), "meta": {"summary": result.get("summary")}}