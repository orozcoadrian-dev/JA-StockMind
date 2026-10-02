from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CanonicalProduct, LinkStatus, Origin, ProductLink
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

    left_category = getattr(product, "category", None)
    right_category = getattr(other, "category", None)
    left_category_id = getattr(product, "category_id", None)
    right_category_id = getattr(other, "category_id", None)
    same_category = bool(
        (left_category and right_category and normalize_name(left_category) == normalize_name(right_category))
        or (left_category_id and left_category_id == right_category_id)
    )
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


def _persist_pending_match(db: Session, product, candidate, confidence: float, reasons: list[str]) -> None:
    source_canonical_ids = set(db.scalars(select(ProductLink.canonical_product_id).where(
        ProductLink.product_id == product.id,
        ProductLink.status == LinkStatus.PENDING,
    )).all())
    candidate_canonical_ids = set(db.scalars(select(ProductLink.canonical_product_id).where(
        ProductLink.product_id == candidate.id,
        ProductLink.status == LinkStatus.PENDING,
    )).all())
    shared_ids = source_canonical_ids & candidate_canonical_ids
    canonical = db.get(CanonicalProduct, min(shared_ids)) if shared_ids else None
    if canonical is None:
        name = choose_match_name(product, candidate)
        category_ids = [value for value in (getattr(product, "category_id", None), getattr(candidate, "category_id", None)) if value]
        canonical = CanonicalProduct(
            canonical_name=name,
            category_id=category_ids[0] if category_ids and len(set(category_ids)) == 1 else None,
            attributes=extract_attributes(name),
        )
        db.add(canonical)
        db.flush()

    for item in (product, candidate):
        link = db.scalar(select(ProductLink).where(
            ProductLink.product_id == item.id,
            ProductLink.canonical_product_id == canonical.id,
        ))
        if link is None:
            db.add(ProductLink(
                product_id=item.id,
                canonical_product_id=canonical.id,
                confidence=confidence,
                origin=Origin.AGENT_SUGGESTION,
                status=LinkStatus.PENDING,
                reasons=reasons,
            ))


def choose_match_name(product, candidate) -> str:
    return max((product.raw_name.strip(), candidate.raw_name.strip()), key=lambda name: (len(name.split()), len(name)))


def find_candidates(
    product,
    candidates: Iterable | None = None,
    db: Session | None = None,
) -> list[tuple[object, float, list[str]]]:
    """Compare supplier products and persist automatic or review decisions when given a session."""
    candidates = candidates or []
    results = []
    for candidate in candidates:
        if candidate.supplier_id == product.supplier_id:
            continue
        score, reasons = compare_products(product, candidate)
        decision = decision_for_score(score)
        if decision != "discard":
            rounded_score = round(score, 4)
            results.append((candidate, rounded_score, reasons))
            if db is not None and decision == "review":
                _persist_pending_match(db, product, candidate, rounded_score, reasons)
    return sorted(results, key=lambda item: item[1], reverse=True)