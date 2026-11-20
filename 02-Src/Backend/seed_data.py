from datetime import date

from sqlalchemy import select

from Backend.database import SessionLocal, init_db
from Backend.Models.canonical_product import CanonicalProduct
from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.product import Product
from Backend.Models.supplier import Supplier


def seed_data():
    init_db()
    db = SessionLocal()

    try:
        existing_suppliers = db.execute(select(Supplier.id)).scalars().all()
        if existing_suppliers:
            return

        suppliers = [
            Supplier(name="Inversiones Guerrero", nit="900123456-7", contact="Carlos Ruiz", active=True),
            Supplier(name="Malusa", nit="900654321-9", contact="Ana Gómez", active=True),
            Supplier(name="Distrimotos", nit="901987654-2", contact="Jorge Torres", active=True),
            Supplier(name="Partes del Caribe", nit="902456789-5", contact="Laura Peña", active=True),
        ]
        db.add_all(suppliers)
        db.flush()

        categories = ["manillar", "frenos", "iluminacion"]
        for category in categories:
            db.add(CanonicalProduct(name=f"{category.title()} base", category=category, attributes={"type": category}, stock_in_bodega=0, minimum_stock=0))

        db.add_all(
            [
                Product(
                    supplier_id=1,
                    provider_code="IG-4471",
                    raw_name="GRIP ROJO DEPORTIVO",
                    normalized_name="grip rojo deportivo",
                    category="manillar",
                    unit_price=185000,
                    currency="COP",
                    unit_of_measure="unidad",
                    pack_quantity=1,
                    price_list_date=date(2026, 9, 1),
                    row_hash="hash_ig_4471",
                ),
                Product(
                    supplier_id=2,
                    provider_code="ML-0892",
                    raw_name="Manubrio grip rojo",
                    normalized_name="manubrio grip rojo",
                    category="manillar",
                    unit_price=190000,
                    currency="COP",
                    unit_of_measure="unidad",
                    pack_quantity=1,
                    price_list_date=date(2026, 9, 1),
                    row_hash="hash_ml_0892",
                ),
                Product(
                    supplier_id=3,
                    provider_code="DT-5510",
                    raw_name="Freno delantero",
                    normalized_name="freno delantero",
                    category="frenos",
                    unit_price=260000,
                    currency="COP",
                    unit_of_measure="unidad",
                    pack_quantity=1,
                    price_list_date=date(2026, 9, 1),
                    row_hash="hash_dt_5510",
                ),
            ]
        )

        db.add(
            EquivalenceRule(
                original_text="si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo",
                structured_condition={
                    "type": "supplier_equivalence",
                    "match": {"keywords": ["grip", "rojo"], "attributes": {"color": "rojo", "type": "grip"}},
                    "suppliers": ["Inversiones Guerrero", "Malusa"],
                    "action": "merge_to_canonical",
                    "confidence": 1.0,
                },
                supplier_names=["Inversiones Guerrero", "Malusa"],
                active=True,
            )
        )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
    print("Seed data loaded successfully.")
