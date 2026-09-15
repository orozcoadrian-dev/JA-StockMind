from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select

from Backend.Models.canonical_product import CanonicalProduct
from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.match_suggestion import MatchSuggestion
from Backend.Models.product import Product
from Backend.Models.product_link import ProductLink
from Backend.Models.supplier import Supplier
from Backend.Services.consolidator import consolidate_products
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.importer import import_excel_file
from Backend.Services.matcher import find_candidates
from Backend.Services.normalizer import normalize_name
from Backend.Services.rules_engine import apply_rules
from Backend.database import SessionLocal


class ImportExcelParams(BaseModel):
    file_id: str = Field(min_length=1)
    supplier_id: int = Field(gt=0)


class SearchProductsParams(BaseModel):
    query: str = Field(min_length=1)
    supplier_id: int | None = Field(default=None, gt=0)
    category: str | None = None


class IdParams(BaseModel):
    id: int = Field(gt=0)


class SuggestMatchesParams(BaseModel):
    product_id: int | None = Field(default=None, gt=0)


class NaturalRuleParams(BaseModel):
    natural_text: str = Field(min_length=5, max_length=500)


class ConsolidateParams(BaseModel):
    product_ids: list[int] = Field(min_length=2)
    canonical_name: str = Field(min_length=2, max_length=300)


class InventoryParams(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class PurchaseParams(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    categories: list[str] | None = None


TOOL_SCHEMAS = {
    "import_excel": {"name": "import_excel", "description": "Importa una lista Excel de proveedor.", "parameters": ImportExcelParams.model_json_schema()},
    "search_products": {"name": "search_products", "description": "Busca productos importados.", "parameters": SearchProductsParams.model_json_schema()},
    "get_canonical_product": {"name": "get_canonical_product", "description": "Consulta un producto canónico y sus proveedores.", "parameters": IdParams.model_json_schema()},
    "suggest_matches": {"name": "suggest_matches", "description": "Calcula sugerencias de equivalencia.", "parameters": SuggestMatchesParams.model_json_schema()},
    "create_equivalence_rule": {"name": "create_equivalence_rule", "description": "Interpreta una regla y la deja pendiente de confirmación.", "parameters": NaturalRuleParams.model_json_schema()},
    "list_rules": {"name": "list_rules", "description": "Lista reglas activas e históricas.", "parameters": {"type": "object", "properties": {}}},
    "consolidate": {"name": "consolidate", "description": "Consolida productos; siempre exige confirmación.", "parameters": ConsolidateParams.model_json_schema()},
    "get_inventory_report": {"name": "get_inventory_report", "description": "Genera un reporte de inventario real.", "parameters": InventoryParams.model_json_schema()},
    "compare_supplier_prices": {"name": "compare_supplier_prices", "description": "Compara precios de un producto canónico.", "parameters": IdParams.model_json_schema()},
    "get_purchase_suggestions": {"name": "get_purchase_suggestions", "description": "Sugiere compras con base en stock y precios.", "parameters": PurchaseParams.model_json_schema()},
}


def _product_data(product: Product) -> dict:
    return {"id": product.id, "supplier_id": product.supplier_id, "provider_code": product.provider_code, "name": product.raw_name, "normalized_name": product.normalized_name, "category": product.category, "unit_price": float(product.unit_price)}


def _canonical_data(canonical: CanonicalProduct, db) -> dict:
    links = db.scalars(select(ProductLink).where(ProductLink.canonical_product_id == canonical.id)).all()
    return {"id": canonical.id, "name": canonical.name, "category": canonical.category, "attributes": canonical.attributes, "stock_in_bodega": canonical.stock_in_bodega, "suppliers": [_product_data(db.get(Product, link.product_id)) for link in links]}


def _rule_from_text(text: str) -> dict:
    normalized = normalize_name(text)
    supplier_options = ["Inversiones Guerrero", "Malusa", "Distrimotos", "Partes del Caribe"]
    suppliers = [supplier for supplier in supplier_options if normalize_name(supplier) in normalized]
    keywords = [word for word in ("grip", "rojo", "azul", "freno", "filtro") if word in normalized]
    attributes = {}
    if "rojo" in keywords:
        attributes["color"] = "rojo"
    if "azul" in keywords:
        attributes["color"] = "azul"
    if "grip" in keywords:
        attributes["type"] = "grip"
    exclusion = any(token in normalized for token in ("no fusionar", "no son el mismo", "excluir"))
    category = "frenos" if "freno" in normalized else None
    if category:
        action = "prefer_supplier"
        rule_type = "purchase_preference"
    elif exclusion:
        action = "block_merge"
        rule_type = "exclusion"
    else:
        action = "merge_to_canonical"
        rule_type = "supplier_equivalence"
    match = {"keywords": keywords, "attributes": attributes}
    if category:
        match["category"] = category
    return {"type": rule_type, "match": match, "suppliers": suppliers, "action": action, "confidence": 1.0}


def _suggest_for_products(db, products: list[Product]) -> list[dict]:
    suggestions = []
    for index, product in enumerate(products):
        for candidate, score, reasons in find_candidates(product, products[index + 1:]):
            first_id, second_id = sorted((product.id, candidate.id))
            row = db.scalar(select(MatchSuggestion).where(MatchSuggestion.product_id == first_id, MatchSuggestion.candidate_product_id == second_id))
            if row is None:
                row = MatchSuggestion(product_id=first_id, candidate_product_id=second_id, score=score, reasons=reasons, decision="automatic" if score > 0.90 else "review")
                db.add(row)
            suggestions.append({"product_id": first_id, "candidate_product_id": second_id, "score": score, "reasons": reasons})
    return suggestions


def _execute(name: str, params: BaseModel, db, confirmed: bool = False) -> dict:
    if name == "import_excel":
        data = import_excel_file(Path(params.file_id), params.supplier_id)
        return {"summary": f"Se importaron {data['imported_rows']} filas.", "data": data}
    if name == "search_products":
        query = f"%{normalize_name(params.query)}%"
        statement = select(Product).where(or_(Product.normalized_name.ilike(query), Product.raw_name.ilike(f"%{params.query}%")))
        if params.supplier_id:
            statement = statement.where(Product.supplier_id == params.supplier_id)
        if params.category:
            statement = statement.where(Product.category == params.category)
        products = db.scalars(statement.limit(100)).all()
        return {"summary": f"Se encontraron {len(products)} productos.", "data": [_product_data(product) for product in products]}
    if name == "get_canonical_product":
        canonical = db.get(CanonicalProduct, params.id)
        if canonical is None:
            raise ValueError("El producto canónico no existe.")
        return {"summary": "Producto canónico consultado.", "data": _canonical_data(canonical, db)}
    if name == "suggest_matches":
        products = [db.get(Product, params.product_id)] if params.product_id else db.scalars(select(Product)).all()
        products = [product for product in products if product is not None]
        data = _suggest_for_products(db, products)
        return {"summary": f"Se calcularon {len(data)} sugerencias; ninguna fusión fue ejecutada.", "data": data}
    if name == "create_equivalence_rule":
        structured = _rule_from_text(params.natural_text)
        if confirmed:
            rule = EquivalenceRule(
                original_text=params.natural_text,
                structured_condition=structured,
                supplier_names=structured["suppliers"],
                active=True,
            )
            db.add(rule)
            db.flush()
            affected = 0
            if structured["action"] == "merge_to_canonical" and len(structured["suppliers"]) >= 2:
                supplier_ids = db.scalars(select(Supplier.id).where(Supplier.name.in_(structured["suppliers"]))).all()
                products = db.scalars(select(Product).where(Product.supplier_id.in_(supplier_ids))).all()
                for index, product in enumerate(products):
                    for candidate in products[index + 1:]:
                        if product.supplier_id == candidate.supplier_id:
                            continue
                        decision = apply_rules(product, db=db, other_product=candidate)
                        if decision["decision"] == "merge" and not decision["conflicts"]:
                            consolidate_products(db, [product, candidate], 1.0, origin="rule", confirmed_by="user")
                            affected += 1
            return {"summary": f"Regla guardada y aplicada a {affected} pares de productos.", "data": {"rule_id": rule.id, "structured_condition": structured, "affected_pairs": affected}}
        return {"summary": "Interpreté la regla; requiere confirmación antes de guardarla.", "data": {"original_text": params.natural_text, "structured_condition": structured, "supplier_names": structured["suppliers"]}, "confirmation_required": True}
    if name == "list_rules":
        rules = db.scalars(select(EquivalenceRule).order_by(EquivalenceRule.id.desc())).all()
        return {"summary": f"Se encontraron {len(rules)} reglas.", "data": [{"id": rule.id, "original_text": rule.original_text, "structured_condition": rule.structured_condition, "active": rule.active, "applied_count": rule.applied_count} for rule in rules]}
    if name == "consolidate":
        if not confirmed:
            return {"summary": "La consolidación es destructiva y requiere confirmación.", "data": {"product_ids": params.product_ids, "canonical_name": params.canonical_name}, "confirmation_required": True}
        products = [db.get(Product, product_id) for product_id in params.product_ids]
        if any(product is None for product in products):
            raise ValueError("Uno o más productos no existen.")
        canonical = consolidate_products(db, products, 1.0, origin="agent", confirmed_by="user")
        canonical.name = params.canonical_name
        return {"summary": "Productos consolidados con confirmación.", "data": _canonical_data(canonical, db)}
    if name == "get_inventory_report":
        statement = select(CanonicalProduct)
        category = params.filters.get("category")
        if category:
            statement = statement.where(CanonicalProduct.category == category)
        products = db.scalars(statement).all()
        low_stock = [product for product in products if product.stock_in_bodega <= product.minimum_stock]
        return {"summary": f"Reporte de {len(products)} productos canónicos; {len(low_stock)} requieren atención.", "data": {"total_canonical": len(products), "low_stock": [_canonical_data(product, db) for product in low_stock]}}
    if name == "compare_supplier_prices":
        canonical = db.get(CanonicalProduct, params.id)
        if canonical is None:
            raise ValueError("El producto canónico no existe.")
        data = _canonical_data(canonical, db)["suppliers"]
        return {"summary": f"Se compararon {len(data)} precios de proveedores.", "data": sorted(data, key=lambda item: item["unit_price"])}
    if name == "get_purchase_suggestions":
        statement = select(CanonicalProduct)
        if params.categories:
            statement = statement.where(CanonicalProduct.category.in_(params.categories))
        products = db.scalars(statement).all()
        data = [{"canonical_product_id": product.id, "name": product.name, "category": product.category, "units_to_buy": max(product.minimum_stock - product.stock_in_bodega, 0)} for product in products if product.stock_in_bodega < product.minimum_stock]
        return {"summary": f"Se generaron {len(data)} sugerencias de compra con datos persistidos.", "data": data}
    raise ValueError(f"Herramienta desconocida: {name}")


def execute_tool(name: str, arguments: dict[str, Any], db=None, confirmed: bool = False) -> dict:
    own_session = db is None
    db = db or SessionLocal()
    validators = {
        "import_excel": ImportExcelParams, "search_products": SearchProductsParams, "get_canonical_product": IdParams,
        "suggest_matches": SuggestMatchesParams, "create_equivalence_rule": NaturalRuleParams, "list_rules": lambda **_: None,
        "consolidate": ConsolidateParams, "get_inventory_report": InventoryParams, "compare_supplier_prices": IdParams,
        "get_purchase_suggestions": PurchaseParams,
    }
    try:
        validator = validators.get(name)
        if validator is None:
            raise ValueError(f"Herramienta desconocida: {name}")
        params = validator(**arguments) if name != "list_rules" else None
        result = _execute(name, params, db, confirmed=confirmed)
        if not result.get("confirmation_required"):
            db.commit()
        return result
    except (ValidationError, ValueError) as exc:
        db.rollback()
        return {"summary": "La herramienta no pudo ejecutarse.", "error": str(exc), "data": {}}
    finally:
        if own_session:
            db.close()
