import unittest
import hashlib
import os
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.models import (
    EquivalenceRule as MySQLEquivalenceRule,
    LinkStatus,
    Origin,
    Product as MySQLProduct,
    ProductLink,
    RuleType,
    Supplier as MySQLSupplier,
)
from Backend.Models.product import Product
from Backend.Services.consolidator import consolidate_products, revert_link
from Backend.Services.matcher import compare_products, find_candidates
from Backend.Services.rules_engine import apply_rules

RUN_MYSQL_INTEGRATION = (
    os.getenv("RUN_MYSQL_INTEGRATION") == "1"
    and os.getenv("DB_NAME") == "stockmind_test"
)


def product(product_id, supplier_id, name, price, category="manillar"):
    return Product(
        id=product_id,
        supplier_id=supplier_id,
        provider_code=f"SKU-{product_id}",
        raw_name=name,
        normalized_name=name.lower(),
        category=category,
        unit_price=price,
        currency="COP",
        unit_of_measure="unidad",
        pack_quantity=1,
        price_list_date="2026-09-01",
        row_hash=f"hash-{product_id}",
    )


class MatchingEngineTest(unittest.TestCase):
    def test_red_grips_match_but_blue_and_different_measure_do_not(self):
        guerrero = product(1, 1, "GRIP ROJO DEPORTIVO 22mm", 185000)
        malusa_red = product(2, 2, "Manubrio grip rojo 22mm", 190000)
        malusa_blue = product(3, 2, "Manubrio grip azul 22mm", 190000)
        malusa_different_measure = product(4, 2, "Manubrio grip rojo 28mm", 190000)

        red_score, red_reasons = compare_products(guerrero, malusa_red)
        blue_score, blue_reasons = compare_products(guerrero, malusa_blue)
        measure_score, measure_reasons = compare_products(guerrero, malusa_different_measure)

        self.assertGreater(red_score, 0.90)
        self.assertTrue(any("color" in reason.lower() for reason in red_reasons))
        self.assertLess(blue_score, 0.65)
        self.assertTrue(any("contradic" in reason.lower() for reason in blue_reasons))
        self.assertLess(measure_score, 0.65)
        self.assertTrue(any("medida" in reason.lower() for reason in measure_reasons))

    def test_find_candidates_returns_threshold_and_reasons(self):
        source = product(1, 1, "GRIP ROJO DEPORTIVO 22mm", 185000)
        candidate = product(2, 2, "Manubrio grip rojo 22mm", 190000)

        results = find_candidates(source, [candidate])

        self.assertEqual(len(results), 1)
        self.assertGreater(results[0][1], 0.90)
        self.assertTrue(results[0][2])

    @unittest.skipUnless(
        RUN_MYSQL_INTEGRATION,
        "Activa RUN_MYSQL_INTEGRATION=1 y DB_NAME=stockmind_test para probar MySQL.",
    )
    def test_mysql_review_rule_consolidation_and_reversal(self):
        from app.db.session import SessionLocal

        db = SessionLocal()
        suffix = uuid4().hex[:12]
        try:
            source_supplier = MySQLSupplier(name=f"Prueba origen {suffix}")
            candidate_supplier = MySQLSupplier(name=f"Prueba candidato {suffix}")
            db.add_all([source_supplier, candidate_supplier])
            db.flush()
            source = MySQLProduct(
                supplier_id=source_supplier.id,
                raw_name="GRIP ROJO DEPORTIVO 22mm",
                normalized_name="grip rojo deportivo 22mm",
                unit_price=Decimal("10000.00"),
                currency="COP",
                pack_quantity=1,
                row_hash=hashlib.sha256(f"source-{suffix}".encode()).hexdigest(),
            )
            candidate = MySQLProduct(
                supplier_id=candidate_supplier.id,
                raw_name="GRIP ROJO UNIVERSAL",
                normalized_name="grip rojo universal",
                unit_price=Decimal("11000.00"),
                currency="COP",
                pack_quantity=1,
                row_hash=hashlib.sha256(f"candidate-{suffix}".encode()).hexdigest(),
            )
            db.add_all([source, candidate])
            db.flush()

            candidates = find_candidates(source, [candidate], db=db)
            self.assertEqual(len(candidates), 1)
            pending_links = db.scalars(select(ProductLink).where(
                ProductLink.product_id.in_([source.id, candidate.id]),
                ProductLink.status == LinkStatus.PENDING,
            )).all()
            self.assertEqual(len(pending_links), 2)
            self.assertTrue(all(link.reasons for link in pending_links))

            db.add(MySQLEquivalenceRule(
                original_text="Tratar grips rojos como equivalentes",
                rule_type=RuleType.EQUIVALENCE,
                condition_json={"match": {"keywords": ["grip"], "attributes": {"color": "rojo"}}},
                suppliers=[source_supplier.name, candidate_supplier.name],
                active=True,
            ))
            db.flush()
            decision = apply_rules(source, db, candidate)
            self.assertEqual(decision["decision"], "merge")

            canonical = consolidate_products(
                db,
                [source, candidate],
                candidates[0][1],
                origin=Origin.RULE,
                confirmed_by="test",
            )
            self.assertTrue(all(link.status == LinkStatus.CONFIRMED for link in pending_links))
            self.assertEqual(pending_links[0].canonical_product_id, canonical.id)
            link_id = pending_links[0].id
            revert_link(db, link_id)
            self.assertIsNone(db.get(ProductLink, link_id))
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()