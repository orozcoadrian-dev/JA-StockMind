from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AgentAction,
    CanonicalProduct,
    Category,
    EquivalenceRule,
    Import,
    LinkStatus,
    Product,
    ProductLink,
    RuleType,
    Supplier,
)
from Backend.Services.consolidator import consolidate_products
from Backend.Services.importer import _save_uploaded_file, import_excel_file
from Backend.Services.matcher import find_candidates


class APIServiceError(Exception):
    def __init__(self, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _not_found(resource: str) -> APIServiceError:
    return APIServiceError(404, f"{resource} no existe.")


def _pagination(query, db: Session, page: int, per_page: int):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    meta = {"total": total, "page": page, "per_page": per_page, "pages": math.ceil(total / per_page) if total else 0}
    return rows, meta


def _supplier_data(item: Supplier) -> dict[str, Any]:
    return {"id": item.id, "name": item.name, "nit": item.nit, "contact": item.contact, "active": item.active, "created_at": item.created_at.isoformat()}


def _product_data(db: Session, item: Product) -> dict[str, Any]:
    category = db.get(Category, item.category_id) if item.category_id else None
    return {
        "id": item.id,
        "supplier_id": item.supplier_id,
        "provider_code": item.supplier_code,
        "raw_name": item.raw_name,
        "normalized_name": item.normalized_name,
        "category": category.name if category else None,
        "unit_price": float(item.unit_price),
        "currency": item.currency,
        "unit_of_measure": item.unit,
        "pack_quantity": item.pack_quantity,
        "price_list_date": item.price_list_date.isoformat() if item.price_list_date else None,
        "row_hash": item.row_hash,
    }


def _canonical_data(db: Session, item: CanonicalProduct) -> dict[str, Any]:
    category = db.get(Category, item.category_id) if item.category_id else None
    linked_products = db.scalars(
        select(Product).join(ProductLink, ProductLink.product_id == Product.id)
        .where(ProductLink.canonical_product_id == item.id)
    ).all()
    return {
        "id": item.id,
        "name": item.canonical_name,
        "category": category.name if category else None,
        "attributes": item.attributes or {},
        "stock_in_bodega": item.stock,
        "minimum_stock": item.min_stock,
        "suppliers": [_product_data(db, product) for product in linked_products],
    }


def _rule_data(item: EquivalenceRule) -> dict[str, Any]:
    return {
        "id": item.id,
        "original_text": item.original_text,
        "structured_condition": item.condition_json,
        "supplier_names": item.suppliers or [],
        "active": item.active,
        "created_at": item.created_at.isoformat(),
        "applied_count": item.times_applied,
    }


def _import_data(item: Import) -> dict[str, Any]:
    summary = {
        "read_rows": item.rows_read,
        "imported_rows": item.rows_imported,
        "updated_rows": item.rows_updated,
        "rejected_rows": item.rejection_report or [],
        "status": item.status.value,
    }
    return {
        "id": item.id,
        "supplier_id": item.supplier_id,
        "filename": item.original_filename,
        "stored_file_path": item.stored_path,
        "summary": summary,
        "created_at": item.created_at.isoformat(),
    }


def list_suppliers(db: Session, page: int, per_page: int):
    rows, meta = _pagination(select(Supplier).order_by(Supplier.id), db, page, per_page)
    return [_supplier_data(row) for row in rows], meta


def create_supplier(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    item = Supplier(**values)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIServiceError(409, "El proveedor o NIT ya existe.") from exc
    db.refresh(item)
    return _supplier_data(item)


def get_supplier(db: Session, supplier_id: int) -> dict[str, Any]:
    item = db.get(Supplier, supplier_id)
    if item is None:
        raise _not_found("El proveedor")
    return _supplier_data(item)


def update_supplier(db: Session, supplier_id: int, values: dict[str, Any]) -> dict[str, Any]:
    item = db.get(Supplier, supplier_id)
    if item is None:
        raise _not_found("El proveedor")
    for key, value in values.items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIServiceError(409, "El proveedor o NIT ya existe.") from exc
    db.refresh(item)
    return _supplier_data(item)


def delete_supplier(db: Session, supplier_id: int) -> None:
    item = db.get(Supplier, supplier_id)
    if item is None:
        raise _not_found("El proveedor")
    if db.scalar(select(Product.id).where(Product.supplier_id == supplier_id).limit(1)):
        raise APIServiceError(409, "No se puede borrar un proveedor con productos.")
    db.delete(item)
    db.commit()


def create_import(db: Session, supplier_id: int, filename: str, contents: bytes) -> dict[str, Any]:
    if db.get(Supplier, supplier_id) is None:
        raise _not_found("El proveedor")
    if Path(filename).suffix.lower() != ".xlsx":
        raise APIServiceError(422, "La extensión del archivo no es válida. Usa .xlsx.")
    try:
        workbook = load_workbook(BytesIO(contents), read_only=True, data_only=True)
        workbook.close()
    except Exception as exc:
        raise APIServiceError(422, "El archivo no es un libro Excel .xlsx válido.") from exc

    stored_path = _save_uploaded_file(BytesIO(contents), filename)
    try:
        summary = import_excel_file(stored_path, supplier_id, db, original_filename=filename, stored_path=stored_path)
    except Exception:
        Path(stored_path).unlink(missing_ok=True)
        raise
    item = db.get(Import, summary["import_id"])
    return _import_data(item)


def list_imports(db: Session, page: int, per_page: int, supplier_id: int | None):
    query = select(Import).order_by(Import.created_at.desc())
    if supplier_id is not None:
        query = query.where(Import.supplier_id == supplier_id)
    rows, meta = _pagination(query, db, page, per_page)
    return [_import_data(row) for row in rows], meta


def get_import(db: Session, import_id: int) -> dict[str, Any]:
    item = db.get(Import, import_id)
    if item is None:
        raise _not_found("La importación")
    return _import_data(item)


def list_products(db: Session, page: int, per_page: int, query: str | None, supplier_id: int | None, category: str | None, sort: str):
    statement = select(Product)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Product.normalized_name.ilike(pattern), Product.raw_name.ilike(pattern)))
    if supplier_id is not None:
        statement = statement.where(Product.supplier_id == supplier_id)
    if category:
        statement = statement.join(Category, Category.id == Product.category_id).where(Category.name == category)
    columns = {"id": Product.id, "price": Product.unit_price, "name": Product.normalized_name, "category": Product.category_id}
    sort_key = sort.lstrip("-")
    order_column = columns.get(sort_key)
    if order_column is None:
        raise APIServiceError(422, "El campo de orden no es válido.", {"allowed": sorted(columns)})
    statement = statement.order_by(order_column.desc() if sort.startswith("-") else order_column)
    rows, meta = _pagination(statement, db, page, per_page)
    return [_product_data(db, row) for row in rows], meta


def get_product(db: Session, product_id: int) -> dict[str, Any]:
    item = db.get(Product, product_id)
    if item is None:
        raise _not_found("El producto")
    return _product_data(db, item)


def _category_id(db: Session, category_name: str | None) -> int | None:
    if not category_name:
        return None
    category_id = db.scalar(select(Category.id).where(func.lower(Category.name) == category_name.lower()))
    if category_id is None:
        raise APIServiceError(400, "La categoría indicada no existe.", {"category": category_name})
    return category_id


def list_canonical_products(db: Session, page: int, per_page: int, category: str | None):
    query = select(CanonicalProduct).order_by(CanonicalProduct.id)
    if category:
        query = query.join(Category, Category.id == CanonicalProduct.category_id).where(Category.name == category)
    rows, meta = _pagination(query, db, page, per_page)
    return [_canonical_data(db, row) for row in rows], meta


def create_canonical_product(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    category_id = _category_id(db, values.pop("category", None))
    item = CanonicalProduct(
        canonical_name=values.pop("name"),
        category_id=category_id,
        attributes=values.get("attributes") or None,
        stock=values.pop("stock_in_bodega", 0),
        min_stock=values.pop("minimum_stock", 0),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _canonical_data(db, item)


def get_canonical_product(db: Session, canonical_id: int) -> dict[str, Any]:
    item = db.get(CanonicalProduct, canonical_id)
    if item is None:
        raise _not_found("El producto canónico")
    return _canonical_data(db, item)


def update_canonical_product(db: Session, canonical_id: int, values: dict[str, Any]) -> dict[str, Any]:
    item = db.get(CanonicalProduct, canonical_id)
    if item is None:
        raise _not_found("El producto canónico")
    if "category" in values:
        item.category_id = _category_id(db, values.pop("category"))
    mapping = {"name": "canonical_name", "stock_in_bodega": "stock", "minimum_stock": "min_stock"}
    for key, value in values.items():
        setattr(item, mapping.get(key, key), value)
    db.commit()
    db.refresh(item)
    return _canonical_data(db, item)


def canonical_suppliers(db: Session, canonical_id: int) -> list[dict[str, Any]]:
    item = db.get(CanonicalProduct, canonical_id)
    if item is None:
        raise _not_found("El producto canónico")
    return _canonical_data(db, item)["suppliers"]


def suggest_matches(db: Session) -> list[dict[str, Any]]:
    products = db.scalars(select(Product).order_by(Product.id)).all()
    suggestions = []
    for index, product in enumerate(products):
        for candidate, score, reasons in find_candidates(product, products[index + 1 :], db=db):
            suggestions.append({"product_id": product.id, "candidate_product_id": candidate.id, "score": score, "reasons": reasons, "status": "pending"})
    db.commit()
    return suggestions


def _pending_link(db: Session, link_id: int) -> ProductLink:
    item = db.get(ProductLink, link_id)
    if item is None:
        raise _not_found("La coincidencia")
    if item.status != LinkStatus.PENDING:
        raise APIServiceError(409, "La coincidencia ya fue resuelta.")
    return item


def list_pending_matches(db: Session, page: int, per_page: int):
    query = select(ProductLink).where(ProductLink.status == LinkStatus.PENDING).order_by(ProductLink.created_at.desc())
    rows, meta = _pagination(query, db, page, per_page)
    result = []
    for link in rows:
        product = db.get(Product, link.product_id)
        candidate = db.scalar(
            select(Product).join(ProductLink, ProductLink.product_id == Product.id)
            .where(ProductLink.canonical_product_id == link.canonical_product_id, Product.id != link.product_id)
            .limit(1)
        )
        result.append({
            "id": link.id,
            "product": _product_data(db, product),
            "candidate": _product_data(db, candidate) if candidate else _product_data(db, product),
            "score": float(link.confidence),
            "reasons": link.reasons or [],
            "decision": "review",
            "status": link.status.value,
        })
    return result, meta


def confirm_match(db: Session, link_id: int) -> dict[str, Any]:
    link = _pending_link(db, link_id)
    product = db.get(Product, link.product_id)
    canonical_id = link.canonical_product_id
    products = db.scalars(
        select(Product).join(ProductLink, ProductLink.product_id == Product.id)
        .where(ProductLink.canonical_product_id == canonical_id)
    ).all()
    canonical = consolidate_products(db, products or [product], float(link.confidence), origin="manual", confirmed_by="user")
    db.commit()
    return {"suggestion": {"id": link.id, "status": "confirmed"}, "canonical_product": _canonical_data(db, canonical)}


def reject_match(db: Session, link_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    link = _pending_link(db, link_id)
    link.status = LinkStatus.REJECTED
    if payload and payload.get("create_exclusion_rule"):
        product = db.get(Product, link.product_id)
        candidate = db.scalar(
            select(Product).join(ProductLink, ProductLink.product_id == Product.id)
            .where(ProductLink.canonical_product_id == link.canonical_product_id, Product.id != link.product_id)
            .limit(1)
        )
        supplier_names = db.scalars(
            select(Supplier.name).where(Supplier.id.in_({product.supplier_id, candidate.supplier_id}))
        ).all() if candidate else []
        keywords = sorted(set(product.normalized_name.split()) & set(candidate.normalized_name.split())) if candidate else []
        condition = {
            "type": "exclusion",
            "match": {"keywords": keywords or [product.normalized_name]},
            "suppliers": supplier_names,
            "action": "block_merge",
        }
        db.add(EquivalenceRule(
            original_text=payload.get("original_text") or f"No fusionar {product.raw_name} con {candidate.raw_name if candidate else 'otro producto'}",
            rule_type=RuleType.EXCLUSION,
            condition_json=condition,
            suppliers=supplier_names,
            active=True,
        ))
    db.commit()
    return {"id": link.id, "status": "rejected"}


def list_rules(db: Session, page: int, per_page: int):
    rows, meta = _pagination(select(EquivalenceRule).order_by(EquivalenceRule.id.desc()), db, page, per_page)
    return [_rule_data(row) for row in rows], meta


def create_rule(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    condition = values.pop("structured_condition")
    suppliers = values.pop("supplier_names", [])
    rule_type_value = condition.get("type")
    if rule_type_value == "supplier_equivalence":
        rule_type_value = "equivalence"
        condition["type"] = rule_type_value
    if not condition.get("suppliers"):
        condition["suppliers"] = suppliers
    try:
        rule_type = RuleType(rule_type_value)
    except ValueError as exc:
        raise APIServiceError(422, "El tipo de regla no es válido.") from exc
    item = EquivalenceRule(
        original_text=values["original_text"],
        rule_type=rule_type,
        condition_json=condition,
        suppliers=suppliers or condition.get("suppliers"),
        active=values.get("active", True),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _rule_data(item)


def get_rule(db: Session, rule_id: int) -> dict[str, Any]:
    item = db.get(EquivalenceRule, rule_id)
    if item is None:
        raise _not_found("La regla")
    return _rule_data(item)


def update_rule(db: Session, rule_id: int, values: dict[str, Any]) -> dict[str, Any]:
    item = db.get(EquivalenceRule, rule_id)
    if item is None:
        raise _not_found("La regla")
    if "structured_condition" in values:
        condition = values.pop("structured_condition")
        if condition.get("type") == "supplier_equivalence":
            condition["type"] = "equivalence"
        item.condition_json = condition
        item.rule_type = RuleType(condition.get("type"))
    if "supplier_names" in values:
        item.suppliers = values.pop("supplier_names")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _rule_data(item)


def delete_rule(db: Session, rule_id: int) -> None:
    item = db.get(EquivalenceRule, rule_id)
    if item is None:
        raise _not_found("La regla")
    db.delete(item)
    db.commit()


def inventory_report(db: Session, category: str | None) -> dict[str, Any]:
    query = select(CanonicalProduct)
    if category:
        query = query.join(Category, Category.id == CanonicalProduct.category_id).where(Category.name == category)
    products = db.scalars(query).all()
    low_stock = [product for product in products if product.stock <= product.min_stock]
    return {"total_canonical": len(products), "low_stock": [_canonical_data(db, product) for product in low_stock]}


def price_comparison(db: Session, canonical_id: int) -> list[dict[str, Any]]:
    canonical = db.get(CanonicalProduct, canonical_id)
    if canonical is None:
        raise _not_found("El producto canónico")
    products = db.scalars(
        select(Product).join(ProductLink, ProductLink.product_id == Product.id)
        .where(ProductLink.canonical_product_id == canonical_id, ProductLink.status == LinkStatus.CONFIRMED)
    ).all()
    return sorted((_product_data(db, product) for product in products), key=lambda product: product["unit_price"])


def purchase_suggestions(db: Session, budget: Decimal | None, categories: list[str] | None) -> list[dict[str, Any]]:
    query = select(CanonicalProduct)
    if categories:
        query = query.join(Category, Category.id == CanonicalProduct.category_id).where(Category.name.in_(categories))
    products = db.scalars(query).all()
    suggestions = []
    for product in products:
        units_to_buy = max(product.min_stock - product.stock, 0)
        if not units_to_buy:
            continue
        unit_price = db.scalar(
            select(func.min(Product.unit_price))
            .join(ProductLink, ProductLink.product_id == Product.id)
            .where(
                ProductLink.canonical_product_id == product.id,
                ProductLink.status == LinkStatus.CONFIRMED,
            )
        )
        estimated_cost = unit_price * units_to_buy if unit_price is not None else None
        if budget is not None and estimated_cost is not None and estimated_cost > budget:
            continue
        category = db.get(Category, product.category_id) if product.category_id else None
        suggestions.append({
            "canonical_product_id": product.id,
            "name": product.canonical_name,
            "category": category.name if category else None,
            "units_to_buy": units_to_buy,
            "estimated_cost": float(estimated_cost) if estimated_cost is not None else None,
        })
    return suggestions


def list_agent_actions(db: Session, page: int, per_page: int):
    query = select(AgentAction).order_by(AgentAction.created_at.desc())
    rows, meta = _pagination(query, db, page, per_page)
    data = [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat(),
            "tool_name": row.tool,
            "input_payload": row.input_params,
            "result": row.result,
            "required_confirmation": row.required_confirmation,
            "approved": row.approved,
        }
        for row in rows
    ]
    return data, meta
