from __future__ import annotations

from sqlalchemy import select

from Backend.Models.canonical_product import CanonicalProduct
from Backend.Models.product import Product
from Backend.Models.product_link import ProductLink
from Backend.Services.normalizer import extract_attributes


def choose_canonical_name(products: list[Product]) -> str:
    return max(
        (product.raw_name.strip() for product in products),
        key=lambda name: (len(name.split()), len(name), sum(character.isalpha() for character in name)),
    )


def consolidate_products(db, products: list[Product], confidence: float, origin: str = "suggestion", confirmed_by: str | None = None) -> CanonicalProduct:
    if not products:
        raise ValueError("Se requiere al menos un producto para consolidar.")
    categories = [product.category for product in products if product.category]
    canonical = db.scalar(
        select(CanonicalProduct).join(ProductLink, ProductLink.canonical_product_id == CanonicalProduct.id)
        .where(ProductLink.product_id == products[0].id)
    )
    if canonical is None:
        canonical = CanonicalProduct(
            name=choose_canonical_name(products),
            category=max(set(categories), key=categories.count) if categories else "general",
            attributes=extract_attributes(choose_canonical_name(products)),
        )
        db.add(canonical)
        db.flush()

    for product in products:
        link = db.scalar(select(ProductLink).where(ProductLink.product_id == product.id))
        if link is None:
            db.add(ProductLink(
                product_id=product.id,
                canonical_product_id=canonical.id,
                confidence=max(0.0, min(1.0, confidence)),
                origin=origin,
                confirmed_by=confirmed_by,
            ))
    db.flush()
    return canonical


def revert_link(db, link_id: int) -> None:
    link = db.get(ProductLink, link_id)
    if link is None:
        raise ValueError("El vínculo no existe.")
    db.delete(link)
    db.flush()