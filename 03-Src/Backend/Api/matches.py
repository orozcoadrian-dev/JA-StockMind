from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.match_suggestion import MatchSuggestion
from Backend.Models.product import Product
from Backend.database import SessionLocal
from Backend.Services.consolidator import consolidate_products
from Backend.Services.matcher import find_candidates

router = APIRouter(prefix="/api/matches", tags=["matches"])


class RejectRequest(BaseModel):
    create_exclusion_rule: bool = False
    original_text: str | None = Field(default=None, max_length=500)


def _product_data(product: Product) -> dict:
    return {
        "id": product.id,
        "supplier_id": product.supplier_id,
        "provider_code": product.provider_code,
        "raw_name": product.raw_name,
        "normalized_name": product.normalized_name,
        "category": product.category,
        "unit_price": float(product.unit_price),
    }


def _suggestion_data(suggestion: MatchSuggestion, db) -> dict:
    return {
        "id": suggestion.id,
        "product": _product_data(db.get(Product, suggestion.product_id)),
        "candidate": _product_data(db.get(Product, suggestion.candidate_product_id)),
        "score": suggestion.score,
        "reasons": suggestion.reasons,
        "decision": suggestion.decision,
        "status": suggestion.status,
    }


@router.post("/suggest")
def suggest_matches():
    db = SessionLocal()
    try:
        products = db.scalars(select(Product).order_by(Product.id)).all()
        created = 0
        for index, product in enumerate(products):
            candidates = [candidate for candidate in products[index + 1:] if candidate.supplier_id != product.supplier_id]
            for candidate, score, reasons in find_candidates(product, candidates):
                first_id, second_id = sorted((product.id, candidate.id))
                suggestion = db.scalar(select(MatchSuggestion).where(
                    MatchSuggestion.product_id == first_id,
                    MatchSuggestion.candidate_product_id == second_id,
                ))
                if suggestion is None:
                    suggestion = MatchSuggestion(
                        product_id=first_id,
                        candidate_product_id=second_id,
                        score=score,
                        reasons=reasons,
                        decision="automatic" if score > 0.90 else "review",
                    )
                    db.add(suggestion)
                    created += 1
                elif suggestion.status == "pending":
                    suggestion.score = score
                    suggestion.reasons = reasons
                    suggestion.decision = "automatic" if score > 0.90 else "review"
        db.commit()
        return {"data": {"created": created}, "meta": {"total": created}}
    finally:
        db.close()


@router.get("/pending")
def pending_matches():
    db = SessionLocal()
    try:
        suggestions = db.scalars(select(MatchSuggestion).where(MatchSuggestion.status == "pending").order_by(MatchSuggestion.score.desc())).all()
        return {"data": [_suggestion_data(item, db) for item in suggestions], "meta": {"total": len(suggestions)}}
    finally:
        db.close()


@router.post("/{suggestion_id}/confirm")
def confirm_match(suggestion_id: int):
    db = SessionLocal()
    try:
        suggestion = db.get(MatchSuggestion, suggestion_id)
        if suggestion is None:
            raise HTTPException(status_code=404, detail="La sugerencia no existe.")
        if suggestion.status != "pending":
            raise HTTPException(status_code=409, detail="La sugerencia ya fue resuelta.")
        products = [db.get(Product, suggestion.product_id), db.get(Product, suggestion.candidate_product_id)]
        consolidate_products(db, products, suggestion.score, origin="manual_confirmation", confirmed_by="user")
        suggestion.status = "confirmed"
        suggestion.resolved_at = datetime.utcnow()
        db.commit()
        return {"data": _suggestion_data(suggestion, db), "meta": {}}
    finally:
        db.close()


@router.post("/{suggestion_id}/reject")
def reject_match(suggestion_id: int, payload: RejectRequest | None = None):
    db = SessionLocal()
    try:
        suggestion = db.get(MatchSuggestion, suggestion_id)
        if suggestion is None:
            raise HTTPException(status_code=404, detail="La sugerencia no existe.")
        if suggestion.status != "pending":
            raise HTTPException(status_code=409, detail="La sugerencia ya fue resuelta.")
        if payload and payload.create_exclusion_rule:
            product = db.get(Product, suggestion.product_id)
            candidate = db.get(Product, suggestion.candidate_product_id)
            db.add(EquivalenceRule(
                original_text=payload.original_text or f"No fusionar {product.raw_name} con {candidate.raw_name}",
                structured_condition={
                    "type": "exclusion",
                    "match": {"keywords": list(set(product.normalized_name.split()) & set(candidate.normalized_name.split()))},
                    "suppliers": [],
                    "action": "block_merge",
                    "confidence": 1.0,
                },
                supplier_names=[],
                active=True,
            ))
        suggestion.status = "rejected"
        suggestion.resolved_at = datetime.utcnow()
        db.commit()
        return {"data": _suggestion_data(suggestion, db), "meta": {}}
    finally:
        db.close()