from __future__ import annotations

from sqlalchemy import select

from . import SessionLocal, init_db
from .models import CanonicalProduct, Supplier


SUPPLIER_NAMES = ("Inversiones Guerrero", "Malusa", "Distrimotos", "Partes del Caribe")
CATEGORIES = ("Accesorios", "Frenos", "Motor")


def seed_database() -> None:
    init_db()
    with SessionLocal.begin() as session:
        existing_suppliers = set(session.scalars(select(Supplier.name)).all())
        session.add_all(
            Supplier(name=name, is_active=True)
            for name in SUPPLIER_NAMES
            if name not in existing_suppliers
        )

        existing_categories = set(session.scalars(select(CanonicalProduct.category)).all())
        session.add_all(
            CanonicalProduct(canonical_name=f"{category} base", category=category)
            for category in CATEGORIES
            if category not in existing_categories
        )


if __name__ == "__main__":
    seed_database()
    print("MotoStock seed loaded successfully.")