import unittest
import hashlib
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from Backend.Services.api_v1 import APIServiceError, confirm_match, list_pending_matches, suggest_matches
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
from Backend.Services.matcher import compare_products, find_candidates, iter_candidate_pairs
from Backend.Services.normalizer import extract_attributes, normalize_name
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
    def test_confirm_match_unifies_only_the_selected_pair(self):
        products = {
            1: SimpleNamespace(id=1, raw_name="GRIP NEGRO", category_id=1),
            2: SimpleNamespace(id=2, raw_name="GRIP BLACK", category_id=1),
            3: SimpleNamespace(id=3, raw_name="GRIP NG", category_id=1),
        }
        links = [
            SimpleNamespace(
                id=link_id,
                product_id=product_id,
                canonical_product_id=9,
                confidence=Decimal("0.950"),
                status=LinkStatus.PENDING,
                origin=Origin.AGENT_SUGGESTION,
                confirmed_by=None,
            )
            for link_id, product_id in ((1, 1), (2, 2), (3, 3))
        ]
        added = []

        def get(model, item_id):
            if model is ProductLink:
                return next((link for link in links if link.id == item_id), None)
            if model is MySQLProduct:
                return products[item_id]
            return None

        def flush():
            added[-1].id = 10

        db = SimpleNamespace(
            get=get,
            scalars=lambda statement: SimpleNamespace(all=lambda: links),
            add=added.append,
            flush=flush,
            commit=lambda: None,
        )
        canonical = {"id": 10}

        with patch("Backend.Services.api_v1._canonical_data", return_value=canonical):
            result = confirm_match(db, link_id=1, candidate_product_id=2)

        self.assertEqual(result["canonical_product"], canonical)
        self.assertEqual(links[0].canonical_product_id, 10)
        self.assertEqual(links[1].canonical_product_id, 10)
        self.assertEqual(links[0].status, LinkStatus.CONFIRMED)
        self.assertEqual(links[1].status, LinkStatus.CONFIRMED)
        self.assertEqual(links[2].canonical_product_id, 9)
        self.assertEqual(links[2].status, LinkStatus.PENDING)
        self.assertEqual(links[0].origin, Origin.MANUAL)
        self.assertEqual(links[1].origin, Origin.MANUAL)

    def test_confirm_match_rejects_candidate_outside_pending_group(self):
        source = SimpleNamespace(
            id=1,
            product_id=1,
            canonical_product_id=9,
            confidence=Decimal("0.950"),
            status=LinkStatus.PENDING,
        )
        links = [source]
        db = SimpleNamespace(
            get=lambda model, item_id: (
                source if model is ProductLink
                else SimpleNamespace(id=1, raw_name="GRIP NEGRO", category_id=1)
            ),
            scalars=lambda statement: SimpleNamespace(all=lambda: links),
            commit=lambda: self.fail("No debe confirmar una pareja inválida."),
        )

        with self.assertRaises(APIServiceError) as error:
            confirm_match(db, link_id=1, candidate_product_id=2)

        self.assertEqual(error.exception.status_code, 409)

    def test_confirm_match_does_not_reuse_canonical_with_another_confirmed_product(self):
        products = {
            1: SimpleNamespace(id=1, raw_name="GRIP NEGRO", category_id=1),
            2: SimpleNamespace(id=2, raw_name="GRIP BLACK", category_id=1),
        }
        links = [
            SimpleNamespace(
                id=link_id,
                product_id=product_id,
                canonical_product_id=9,
                confidence=Decimal("0.950"),
                status=status,
                origin=Origin.AGENT_SUGGESTION,
            )
            for link_id, product_id, status in (
                (1, 1, LinkStatus.PENDING),
                (2, 2, LinkStatus.PENDING),
                (3, 3, LinkStatus.CONFIRMED),
            )
        ]
        added = []

        def get(model, item_id):
            if model is ProductLink:
                return next((link for link in links if link.id == item_id), None)
            if model is MySQLProduct:
                return products[item_id]
            return None

        def flush():
            added[-1].id = 10

        db = SimpleNamespace(
            get=get,
            scalars=lambda statement: SimpleNamespace(all=lambda: links),
            add=added.append,
            flush=flush,
            commit=lambda: None,
        )
        with patch("Backend.Services.api_v1._canonical_data", return_value={"id": 10}):
            confirm_match(db, link_id=1, candidate_product_id=2)

        self.assertEqual(links[0].canonical_product_id, 10)
        self.assertEqual(links[1].canonical_product_id, 10)
        self.assertEqual(links[2].canonical_product_id, 9)

    def test_color_names_and_abbreviations_normalize_to_same_color(self):
        self.assertEqual(normalize_name("Grip NG"), "grip negro")
        self.assertEqual(normalize_name("Grip black"), "grip negro")
        self.assertEqual(normalize_name("Grip BLUE"), "grip azul")
        self.assertEqual(normalize_name("Grip rojo"), "grip rojo")
        self.assertEqual(normalize_name("yellow grip"), "amarillo grip")
        self.assertEqual(normalize_name("marrón"), "marron")
        self.assertEqual(extract_attributes("Grip NG")["color"], "negro")
        self.assertEqual(extract_attributes("Grip black")["color"], "negro")

    def test_english_and_abbreviated_colors_are_suggested_as_matches(self):
        spanish = product(1, 1, "GRIP NEGRO 22mm", 185000)
        abbreviated = product(2, 2, "GRIP NG 22mm", 190000)
        english = product(3, 3, "HANDLEBAR GRIP BLACK 22mm", 190000)

        abbreviated_score, abbreviated_reasons = compare_products(spanish, abbreviated)
        english_score, english_reasons = compare_products(spanish, english)

        self.assertGreater(abbreviated_score, 0.90)
        self.assertGreater(english_score, 0.90)
        self.assertTrue(any("inglés y abreviaturas" in reason for reason in abbreviated_reasons))
        self.assertTrue(any("inglés y abreviaturas" in reason for reason in english_reasons))

    def test_translated_product_description_matches_spanish_name(self):
        spanish = product(1, 1, "PUÑOS NEGROS DE MANUBRIO 22mm", 185000)
        english = product(2, 2, "HANDLEBAR GRIP BLACK 22mm", 190000)

        score, _ = compare_products(spanish, english)

        self.assertGreater(score, 0.90)

    def test_high_confidence_matches_are_still_persisted_for_confirmation(self):
        spanish = product(1, 1, "GRIP NEGRO 22mm", 185000)
        abbreviated = product(2, 2, "GRIP NG 22mm", 185000)

        with patch("Backend.Services.matcher._persist_pending_match") as persist:
            results = find_candidates(spanish, [abbreviated], db=object())

        self.assertEqual(len(results), 1)
        persist.assert_called_once()

    def test_pending_match_list_shows_each_product_pair_once(self):
        source = SimpleNamespace(
            id=1, supplier_id=1, supplier_code="A1", raw_name="GRIP NEGRO",
            normalized_name="grip negro", category_id=None, unit_price=185000,
            currency="COP", unit="unidad", pack_quantity=1,
            price_list_date=None, row_hash="source",
        )
        candidate = SimpleNamespace(
            id=2, supplier_id=2, supplier_code="B1", raw_name="GRIP NG",
            normalized_name="grip ng", category_id=None, unit_price=185000,
            currency="COP", unit="unidad", pack_quantity=1,
            price_list_date=None, row_hash="candidate",
        )
        links = [
            SimpleNamespace(
                id=link_id, product_id=product_id, canonical_product_id=1,
                confidence=0.95, reasons=["Coincide color"], status=LinkStatus.PENDING,
                created_at=datetime(2026, 1, 1),
            )
            for link_id, product_id in ((1, 1), (2, 2))
        ]
        candidates = iter((candidate, source))
        db = SimpleNamespace(
            scalars=lambda statement: SimpleNamespace(all=lambda: links),
            get=lambda model, product_id: {1: source, 2: candidate}.get(product_id),
            scalar=lambda statement: next(candidates),
        )

        matches, meta = list_pending_matches(db, page=1, per_page=20)

        self.assertEqual(len(matches), 1)
        self.assertEqual(meta["total"], 1)
        self.assertEqual({matches[0]["product"]["id"], matches[0]["candidate"]["id"]}, {1, 2})

    def test_suggest_matches_scans_latest_import_against_other_suppliers(self):
        source = product(10, 1, "GRIP NEGRO 22mm", 185000)
        candidate = product(20, 2, "GRIP BLACK 22mm", 190000)
        query_results = iter(([source], [candidate]))
        db = SimpleNamespace(
            scalar=lambda statement: SimpleNamespace(id=7),
            scalars=lambda statement: SimpleNamespace(all=lambda: next(query_results)),
            commit=lambda: None,
        )
        with (
            patch("Backend.Services.api_v1.iter_candidate_pairs", return_value=[(source, candidate)]) as pairs,
            patch("Backend.Services.api_v1.compare_products", return_value=(0.95, ["Mismo color"])) ,
            patch("Backend.Services.api_v1._persist_pending_match") as persist,
        ):
            suggestions = suggest_matches(db)

        pairs.assert_called_once_with([source, candidate], {source.id})
        persist.assert_called_once_with(db, source, candidate, 0.95, ["Mismo color"])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["score"], 0.95)

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

    def test_candidate_index_limits_comparisons_to_shared_product_terms(self):
        source = product(1, 1, "GRIP NEGRO DEPORTIVO 22mm", 185000)
        same_supplier = product(2, 1, "GRIP NEGRO DEPORTIVO 22mm", 185000)
        candidate = product(3, 2, "HANDLEBAR GRIP BLACK 22mm", 190000)
        unrelated = product(4, 2, "MANUBRIO TUBULAR BWS CARBONO", 28000)

        pairs = list(iter_candidate_pairs(
            [source, same_supplier, candidate, unrelated],
            source_product_ids={source.id},
        ))

        self.assertEqual([(left.id, right.id) for left, right in pairs], [(1, 3)])

    def test_candidate_index_keeps_exactly_equivalent_short_names(self):
        spanish = product(1, 1, "GRIP NEGRO", 185000)
        english = product(2, 2, "GRIP BLACK", 185000)

        pairs = list(iter_candidate_pairs(
            [spanish, english],
            source_product_ids={spanish.id},
        ))

        self.assertEqual([(left.id, right.id) for left, right in pairs], [(1, 2)])

    def test_handlebar_name_does_not_make_tubular_handlebar_a_grip(self):
        grip = product(1, 1, "HANDLEBAR GRIP BLACK 22mm", 185000)
        tubular_handlebar = product(2, 2, "MANUBRIO TUBULAR BWS CARBONO", 28000)

        self.assertNotIn("type", extract_attributes(tubular_handlebar.raw_name))
        self.assertEqual(
            list(iter_candidate_pairs([grip, tubular_handlebar], source_product_ids={grip.id})),
            [],
        )

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