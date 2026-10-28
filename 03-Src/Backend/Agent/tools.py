from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Category, Supplier
from Backend.Services.api_v1 import (
    APIServiceError,
    confirm_match,
    create_rule,
    get_canonical_product,
    inventory_report,
    list_pending_matches,
    list_products,
    list_rules,
    price_comparison,
    purchase_suggestions,
    suggest_matches,
)
from Backend.Services.normalizer import extract_attributes, normalize_name


class SearchProductsParams(BaseModel):
    query: str = Field(min_length=1)
    supplier_id: int | None = Field(default=None, gt=0)
    category: str | None = None


class IdParams(BaseModel):
    id: int = Field(gt=0)


class CompareSupplierPricesParams(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    canonical_product_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_comparison_target(self):
        if bool(self.query) == bool(self.canonical_product_id):
            raise ValueError("Indica un nombre de producto o un ID de producto canónico.")
        return self


class SuggestMatchesParams(BaseModel):
    import_id: int | None = Field(default=None, gt=0)


class NaturalRuleParams(BaseModel):
    natural_text: str = Field(min_length=5, max_length=500)


class ConsolidateParams(BaseModel):
    suggestion_id: int = Field(gt=0)
    candidate_product_id: int = Field(gt=0)


class InventoryParams(BaseModel):
    category: str | None = None


class PurchaseParams(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    categories: list[str] | None = None


TOOL_SCHEMAS = {
    "search_products": {"name": "search_products", "description": "Busca productos importados.", "parameters": SearchProductsParams.model_json_schema()},
    "get_canonical_product": {"name": "get_canonical_product", "description": "Consulta un producto canónico y sus proveedores.", "parameters": IdParams.model_json_schema()},
    "suggest_matches": {"name": "suggest_matches", "description": "Compara la última importación (o el import_id indicado) con productos de otros proveedores; no fusiona productos.", "parameters": SuggestMatchesParams.model_json_schema()},
    "list_pending_matches": {"name": "list_pending_matches", "description": "Lista las coincidencias que esperan revisión humana.", "parameters": {"type": "object", "properties": {}}},
    "create_equivalence_rule": {"name": "create_equivalence_rule", "description": "Interpreta una regla y la deja pendiente de confirmación.", "parameters": NaturalRuleParams.model_json_schema()},
    "list_rules": {"name": "list_rules", "description": "Lista reglas activas e históricas.", "parameters": {"type": "object", "properties": {}}},
    "consolidate": {"name": "consolidate", "description": "Confirma una sugerencia de equivalencia específica; siempre exige confirmación humana.", "parameters": ConsolidateParams.model_json_schema()},
    "get_inventory_report": {"name": "get_inventory_report", "description": "Genera un reporte de inventario real.", "parameters": InventoryParams.model_json_schema()},
    "compare_supplier_prices": {"name": "compare_supplier_prices", "description": "Compara productos por nombre consultando el catálogo, o precios de proveedores para un producto canónico confirmado.", "parameters": CompareSupplierPricesParams.model_json_schema()},
    "get_purchase_suggestions": {"name": "get_purchase_suggestions", "description": "Sugiere compras con base en stock y precios.", "parameters": PurchaseParams.model_json_schema()},
}


def _rule_from_text(text: str, db) -> dict:
    normalized = normalize_name(text)
    supplier_options = db.scalars(select(Supplier.name)).all()
    suppliers = [name for name in supplier_options if normalize_name(name) in normalized]
    supplier_tokens = {token for name in suppliers for token in normalize_name(name).split()}
    stop_words = {
        "si", "un", "una", "el", "la", "los", "las", "de", "del", "y", "o", "es", "son",
        "mismo", "misma", "provee", "proveen", "producto", "productos", "fusionar", "juntar",
        "igual", "prefiero", "preferir", "comprar", "no", "con", "para", "entre",
    }
    keywords = sorted({
        word for word in normalized.split()
        if word not in supplier_tokens and word not in stop_words and len(word) > 1
    })
    attributes = extract_attributes(text)
    categories = db.scalars(select(Category.name)).all()
    category = next((name for name in categories if normalize_name(name) in normalized), None)
    exclusion = any(token in normalized for token in ("no fusionar", "no son el mismo", "excluir"))
    preference = any(token in normalized for token in ("prefiero", "preferir", "comprar primero"))
    rule_type = "exclusion" if exclusion else ("purchase_preference" if preference else "equivalence")
    match = {"keywords": keywords, "attributes": attributes}
    if category:
        match["category"] = category
    return {
        "type": rule_type,
        "match": match,
        "suppliers": suppliers,
        "action": {"exclusion": "block_merge", "purchase_preference": "prefer_supplier"}.get(rule_type, "merge_to_canonical"),
        "confidence": 1.0,
    }


def _execute(name: str, params: BaseModel | None, db, confirmed: bool = False) -> dict:
    if name == "search_products":
        data, meta = list_products(db, 1, 100, normalize_name(params.query), params.supplier_id, params.category, "id")
        return {"summary": f"Se encontraron {meta['total']} productos en el catálogo importado.", "data": data}
    if name == "get_canonical_product":
        return {"summary": "Producto canónico consultado.", "data": get_canonical_product(db, params.id)}
    if name == "suggest_matches":
        data = suggest_matches(db, import_id=params.import_id)
        return {"summary": f"Se calcularon {len(data)} sugerencias; ninguna fusión fue ejecutada.", "data": data}
    if name == "list_pending_matches":
        data, meta = list_pending_matches(db, 1, 100)
        return {"summary": f"Hay {meta['total']} coincidencias pendientes de revisión.", "data": data}
    if name == "create_equivalence_rule":
        structured = _rule_from_text(params.natural_text, db)
        minimum_suppliers = 1 if structured["type"] == "purchase_preference" else 2
        if len(structured["suppliers"]) < minimum_suppliers:
            raise ValueError("No pude identificar los proveedores requeridos en la regla.")
        if not structured["match"]["keywords"] and not structured["match"]["attributes"] and not structured["match"].get("category"):
            raise ValueError("La regla debe describir un producto o una categoría.")
        if not confirmed:
            return {
                "summary": "Interpreté la regla; requiere confirmación antes de guardarla.",
                "data": {"original_text": params.natural_text, "structured_condition": structured, "supplier_names": structured["suppliers"]},
                "confirmation_required": True,
            }
        rule = create_rule(db, {
            "original_text": params.natural_text,
            "structured_condition": structured,
            "supplier_names": structured["suppliers"],
            "active": True,
        })
        suggestions = suggest_matches(db)
        return {"summary": f"Regla guardada y se recalcularon {len(suggestions)} sugerencias de la última importación.", "data": {**rule, "recalculated_suggestions": len(suggestions)}}
    if name == "list_rules":
        data, meta = list_rules(db, 1, 100)
        return {"summary": f"Se encontraron {meta['total']} reglas guardadas.", "data": data}
    if name == "consolidate":
        if not confirmed:
            return {"summary": "La consolidación es destructiva y requiere confirmación.", "data": {"suggestion_id": params.suggestion_id, "candidate_product_id": params.candidate_product_id}, "confirmation_required": True}
        data = confirm_match(db, params.suggestion_id, params.candidate_product_id)
        return {"summary": "Productos consolidados con confirmación.", "data": data}
    if name == "get_inventory_report":
        data = inventory_report(db, params.category)
        return {
            "summary": (
                f"Reporte de {data['total_canonical']} productos canónicos; "
                f"{len(data['low_stock'])} están en o bajo su mínimo y "
                f"{data['without_minimum_count']} no tienen un mínimo configurado."
            ),
            "data": data,
        }
    if name == "compare_supplier_prices":
        if params.canonical_product_id is not None:
            data = price_comparison(db, params.canonical_product_id)
            return {"summary": f"Se compararon {len(data)} precios de proveedores para un producto canónico confirmado.", "data": data}
        data, meta = list_products(db, 1, 100, normalize_name(params.query), None, None, "price")
        supplier_names = {supplier.id: supplier.name for supplier in db.scalars(select(Supplier)).all()}
        for product in data:
            product["supplier_name"] = supplier_names.get(product["supplier_id"], "Proveedor desconocido")
        if not data:
            return {
                "summary": f"No encontré productos que coincidan con '{params.query}'. Importa la lista del proveedor y vuelve a preguntar.",
                "data": [],
            }
        return {
            "summary": f"Encontré {meta['total']} registros para '{params.query}', ordenados por precio. Estos nombres coinciden con la búsqueda, pero no prueban por sí solos que todos sean el mismo producto.",
            "data": data,
        }
    if name == "get_purchase_suggestions":
        budget = Decimal(str(params.budget)) if params.budget is not None else None
        data = purchase_suggestions(db, budget, params.categories)
        if data:
            summary = f"Se generaron {len(data)} sugerencias de compra con stock y precios confirmados disponibles."
        else:
            inventory = inventory_report(db, None)
            if not inventory["total_canonical"]:
                summary = "No hay productos canónicos en el catálogo. Importa listas de proveedores para generar sugerencias de compra."
            elif inventory["without_minimum_count"]:
                summary = (
                    "No hay sugerencias calculables: configura el stock mínimo de los artículos. "
                    f"{inventory['without_minimum_count']} productos aún no tienen mínimo."
                )
            else:
                summary = "No hay artículos bajo su mínimo con los filtros y presupuesto actuales."
        return {"summary": summary, "data": data}
    raise ValueError(f"Herramienta desconocida: {name}")


def execute_tool(name: str, arguments: dict[str, Any], db=None, confirmed: bool = False) -> dict:
    own_session = db is None
    db = db or SessionLocal()
    validators = {
        "search_products": SearchProductsParams, "get_canonical_product": IdParams,
        "compare_supplier_prices": CompareSupplierPricesParams,
        "suggest_matches": SuggestMatchesParams, "list_pending_matches": lambda **_: None,
        "create_equivalence_rule": NaturalRuleParams, "list_rules": lambda **_: None,
        "consolidate": ConsolidateParams, "get_inventory_report": InventoryParams,
        "get_purchase_suggestions": PurchaseParams,
    }
    try:
        validator = validators.get(name)
        if validator is None:
            raise ValueError(f"Herramienta desconocida: {name}")
        params = validator(**arguments) if name not in {"list_rules", "list_pending_matches"} else None
        result = _execute(name, params, db, confirmed=confirmed)
        if not result.get("confirmation_required"):
            db.commit()
        return result
    except (APIServiceError, ValidationError, ValueError) as exc:
        db.rollback()
        return {"summary": "La herramienta no pudo ejecutarse.", "error": str(exc), "data": {}}
    finally:
        if own_session:
            db.close()
