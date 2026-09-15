from __future__ import annotations

from sqlalchemy import select

from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.supplier import Supplier
from Backend.Services.normalizer import extract_attributes, normalize_name


def _matches(rule: EquivalenceRule, product, supplier_name: str | None = None) -> bool:
    condition = rule.structured_condition or {}
    match = condition.get("match", {})
    normalized = normalize_name(product.normalized_name or product.raw_name)
    keywords = [normalize_name(keyword) for keyword in match.get("keywords", [])]
    if any(keyword and keyword not in normalized for keyword in keywords):
        return False

    expected_attributes = match.get("attributes", {})
    attributes = extract_attributes(normalized)
    if any(attributes.get(key) != value for key, value in expected_attributes.items()):
        return False
    if match.get("category") and product.category.lower() != str(match["category"]).lower():
        return False

    suppliers = condition.get("suppliers") or rule.supplier_names or []
    if suppliers and supplier_name and supplier_name not in suppliers:
        return False
    return True


def apply_rules(product, db=None, other_product=None) -> dict:
    """Evalúa reglas para un producto y devuelve una decisión auditable.

    Si se pasa ``other_product``, se exige que ambos proveedores estén incluidos
    en la regla, que es el caso de equivalencias entre proveedores.
    """
    if db is None:
        return {"decision": "none", "matches": [], "conflicts": []}

    supplier = db.get(Supplier, product.supplier_id)
    other_supplier = db.get(Supplier, other_product.supplier_id) if other_product is not None else None
    matches = []
    for rule in db.scalars(select(EquivalenceRule).where(EquivalenceRule.active.is_(True))).all():
        suppliers = rule.structured_condition.get("suppliers") or rule.supplier_names or []
        if other_product is not None and suppliers:
            if not {supplier.name, other_supplier.name}.issubset(set(suppliers)):
                continue
        if _matches(rule, product, supplier.name if supplier else None) and (
            other_product is None or _matches(rule, other_product, other_supplier.name if other_supplier else None)
        ):
            matches.append(rule)

    exclusions = [rule for rule in matches if rule.structured_condition.get("action") == "block_merge"]
    merges = [rule for rule in matches if rule.structured_condition.get("action") == "merge_to_canonical"]
    conflicts = []
    if exclusions and merges:
        conflicts.append("Hay reglas activas de exclusión y equivalencia que coinciden.")
    if len({rule.structured_condition.get("action") for rule in matches}) > 1 and not (exclusions and merges):
        conflicts.append("Hay reglas activas con acciones incompatibles.")

    selected = exclusions[0] if exclusions else (merges[0] if merges else None)
    if selected:
        for rule in matches:
            rule.applied_count += 1
        db.flush()

    return {
        "decision": "exclude" if exclusions else ("merge" if merges else "none"),
        "rule": selected,
        "matches": matches,
        "conflicts": conflicts,
    }