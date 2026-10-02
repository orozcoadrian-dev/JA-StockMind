from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, EquivalenceRule, RuleType, Supplier
from Backend.Services.normalizer import extract_attributes, normalize_name


def _matches(
    rule: EquivalenceRule,
    product,
    supplier_name: str | None = None,
    category_name: str | None = None,
) -> bool:
    condition = rule.condition_json or {}
    match = condition.get("match", {})
    normalized = normalize_name(product.normalized_name or product.raw_name)
    keywords = [normalize_name(keyword) for keyword in match.get("keywords", [])]
    if any(keyword and keyword not in normalized for keyword in keywords):
        return False

    expected_attributes = match.get("attributes", {})
    attributes = extract_attributes(normalized)
    if any(attributes.get(key) != value for key, value in expected_attributes.items()):
        return False
    product_category = getattr(product, "category", None) or category_name
    if match.get("category") and normalize_name(product_category or "") != normalize_name(str(match["category"])):
        return False

    suppliers = condition.get("suppliers") or rule.suppliers or []
    if suppliers and supplier_name and normalize_name(supplier_name) not in {
        normalize_name(name) for name in suppliers
    }:
        return False
    return True


def apply_rules(product, db: Session, other_product=None) -> dict:
    """Evalúa reglas para un producto y devuelve una decisión auditable.

    Si se pasa ``other_product``, se exige que ambos proveedores estén incluidos
    en la regla, que es el caso de equivalencias entre proveedores.
    """
    supplier = db.get(Supplier, product.supplier_id)
    other_supplier = db.get(Supplier, other_product.supplier_id) if other_product is not None else None
    category = db.get(Category, product.category_id) if getattr(product, "category_id", None) else None
    other_category = db.get(Category, other_product.category_id) if other_product is not None and getattr(other_product, "category_id", None) else None
    matches = []
    for rule in db.scalars(select(EquivalenceRule).where(EquivalenceRule.active.is_(True))).all():
        condition = rule.condition_json or {}
        suppliers = condition.get("suppliers") or rule.suppliers or []
        if other_product is not None and suppliers:
            expected = {normalize_name(name) for name in suppliers}
            actual = {
                normalize_name(item.name)
                for item in (supplier, other_supplier)
                if item is not None
            }
            if not actual.issubset(expected) or len(actual) != 2:
                continue
        if _matches(rule, product, supplier.name if supplier else None, category.name if category else None) and (
            other_product is None or _matches(
                rule,
                other_product,
                other_supplier.name if other_supplier else None,
                other_category.name if other_category else None,
            )
        ):
            matches.append(rule)

    exclusions = [rule for rule in matches if rule.rule_type == RuleType.EXCLUSION]
    merges = [rule for rule in matches if rule.rule_type == RuleType.EQUIVALENCE]
    conflicts = []
    if exclusions and merges:
        conflicts.append("Hay reglas activas de exclusión y equivalencia que coinciden.")
    if len({rule.rule_type for rule in matches}) > 1 and not (exclusions and merges):
        conflicts.append("Hay reglas activas con acciones incompatibles.")

    selected = exclusions[0] if exclusions else (merges[0] if merges else None)
    if selected:
        for rule in matches:
            rule.times_applied += 1
        db.flush()

    return {
        "decision": "exclude" if exclusions else ("merge" if merges else "none"),
        "rule": selected,
        "matches": matches,
        "conflicts": conflicts,
    }