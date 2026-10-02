from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CanonicalProduct, LinkStatus, Origin, Product, ProductLink
from Backend.Services.normalizer import extract_attributes


def choose_canonical_name(products: list[Product]) -> str:
    return max(
        (product.raw_name.strip() for product in products),
        key=lambda name: (len(name.split()), len(name), sum(character.isalpha() for character in name)),
    )


def _origin_value(origin: Origin | str) -> Origin:
    if isinstance(origin, Origin):
        return origin
    if origin in {"rule", Origin.RULE.value}:
        return Origin.RULE
    if origin in {"agent", "suggestion", "agent_suggestion", Origin.AGENT_SUGGESTION.value}:
        return Origin.AGENT_SUGGESTION
    return Origin.MANUAL


def consolidate_products(
    db: Session,
    products: list[Product],
    confidence: float,
    origin: Origin | str = Origin.MANUAL,
    confirmed_by: str | None = None,
) -> CanonicalProduct:
    if not products:
        raise ValueError("Se requiere al menos un producto para consolidar.")
    categories = [product.category_id for product in products if product.category_id is not None]
    canonical = db.scalar(
        select(CanonicalProduct).join(ProductLink, ProductLink.canonical_product_id == CanonicalProduct.id)
        .where(ProductLink.product_id == products[0].id)
    )
    if canonical is None:
        canonical_name = choose_canonical_name(products)
        canonical = CanonicalProduct(
            canonical_name=canonical_name,
            category_id=max(set(categories), key=categories.count) if categories else None,
            attributes=extract_attributes(canonical_name),
        )
        db.add(canonical)
        db.flush()

    for product in products:
        link = db.scalar(select(ProductLink).where(
            ProductLink.product_id == product.id,
            ProductLink.canonical_product_id == canonical.id,
        ))
        if link is None:
            link = ProductLink(
                product_id=product.id,
                canonical_product_id=canonical.id,
                confidence=max(0.0, min(1.0, confidence)),
                origin=_origin_value(origin),
                status=LinkStatus.CONFIRMED,
                confirmed_by=confirmed_by,
            )
            db.add(link)
        else:
            link.confidence = max(0.0, min(1.0, confidence))
            link.origin = _origin_value(origin)
            link.status = LinkStatus.CONFIRMED
            link.confirmed_by = confirmed_by
    db.flush()
    return canonical


def revert_link(db: Session, link_id: int) -> None:
    link = db.get(ProductLink, link_id)
    if link is None:
        raise ValueError("El vínculo no existe.")
    db.delete(link)
    db.flush()