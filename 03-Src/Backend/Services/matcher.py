from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from Backend.Services.normalizer import extract_attributes, normalize_name

AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.65


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_name(value)))


def _token_set_ratio(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = " ".join(sorted(left_tokens & right_tokens))
    left_remainder = " ".join(sorted(left_tokens - left_tokens.intersection(right_tokens)))
    right_remainder = " ".join(sorted(right_tokens - left_tokens.intersection(right_tokens)))
    return max(
        SequenceMatcher(None, intersection, " ".join(sorted(left_tokens))).ratio(),
        SequenceMatcher(None, intersection, " ".join(sorted(right_tokens))).ratio(),
        SequenceMatcher(None, left_remainder, right_remainder).ratio(),
    )


def _price_similarity(left: float, right: float) -> float:
    if left <= 0 or right <= 0:
        return 0.0
    difference = abs(left - right) / max(left, right)
    return max(0.0, 1.0 - difference / 0.30)


def compare_products(product, other) -> tuple[float, list[str]]:
    left_name = product.normalized_name or product.raw_name
    right_name = other.normalized_name or other.raw_name
    left_attributes = extract_attributes(left_name)
    right_attributes = extract_attributes(right_name)
    reasons: list[str] = []

    name_score = _token_set_ratio(left_name, right_name)
    reasons.append(f"Similitud de nombre: {name_score:.0%}.")

    matched_attributes = 0
    contradictions = 0
    for attribute in ("color", "measure", "type", "side", "compatible_brand"):
        left_value = left_attributes.get(attribute)
        right_value = right_attributes.get(attribute)
        label = {"measure": "medida", "type": "tipo", "side": "lado", "compatible_brand": "marca"}.get(attribute, attribute)
        if left_value and right_value and left_value == right_value:
            matched_attributes += 1
            reasons.append(f"Coincide el atributo {label}: {left_value}.")
        elif left_value and right_value and left_value != right_value:
            contradictions += 1
            reasons.append(f"Contradicción en {label}: {left_value} frente a {right_value}.")

    compared_attributes = matched_attributes + contradictions
    attribute_score = (matched_attributes / compared_attributes) if compared_attributes else 0.5
    if contradictions:
        attribute_score = max(0.0, attribute_score - 0.5 * contradictions)
    if compared_attributes:
        reasons.append(f"Atributos compatibles: {matched_attributes}/{compared_attributes}.")

    price_score = _price_similarity(float(product.unit_price), float(other.unit_price))
    reasons.append(f"Cercanía de precio: {price_score:.0%}.")

    same_category = bool(product.category and other.category and product.category.lower() == other.category.lower())
    category_score = 1.0 if same_category else 0.0
    reasons.append("Misma categoría." if same_category else "Categorías diferentes.")

    score = (name_score * 0.42) + (attribute_score * 0.48) + (price_score * 0.05) + (category_score * 0.05)
    if matched_attributes >= 3 and not contradictions:
        score += 0.02
    if contradictions:
        score -= 0.25 * contradictions
    score = max(0.0, min(1.0, score))
    return score, reasons


def decision_for_score(score: float) -> str:
    if score > AUTO_THRESHOLD:
        return "automatic"
    if score >= REVIEW_THRESHOLD:
        return "review"
    return "discard"


def find_candidates(product, candidates: Iterable | None = None) -> list[tuple[object, float, list[str]]]:
    """Compara un producto contra productos candidatos de otro proveedor.

    La capa de persistencia puede pasar aquí la consulta ya filtrada; mantener esta
    función pura facilita probar el motor sin abrir una sesión de base de datos.
    """
    candidates = candidates or []
    results = []
    for candidate in candidates:
        if candidate.supplier_id == product.supplier_id:
            continue
        score, reasons = compare_products(product, candidate)
        decision = decision_for_score(score)
        if decision != "discard":
            results.append((candidate, round(score, 4), reasons))
    return sorted(results, key=lambda item: item[1], reverse=True)