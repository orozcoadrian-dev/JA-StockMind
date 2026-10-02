import os
import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.db.base import Base
from app.models import Import, Product, ProductLink
from app.models.enums import ImportStatus, LinkStatus, Origin, RuleType
from app.schemas import EquivalenceRuleCreate, ProductCreate, ProductLinkCreate


class StockMindSchemaTest(unittest.TestCase):
    def test_models_define_exact_target_tables_and_decimal_columns(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "suppliers",
                "categories",
                "imports",
                "products",
                "canonical_products",
                "product_links",
                "equivalence_rules",
                "agent_actions",
            },
        )
        self.assertEqual(Product.__table__.c.unit_price.type.precision, 12)
        self.assertEqual(Product.__table__.c.unit_price.type.scale, 2)
        self.assertEqual(ProductLink.__table__.c.confidence.type.precision, 4)
        self.assertEqual(ProductLink.__table__.c.confidence.type.scale, 3)
        self.assertEqual(Import.__table__.c.status.type.enums, ["processing", "completed", "failed"])
        self.assertEqual([item.value for item in Origin], ["rule", "agent_suggestion", "manual"])
        self.assertEqual([item.value for item in LinkStatus], ["pending", "confirmed", "rejected"])
        self.assertEqual([item.value for item in RuleType], ["equivalence", "exclusion", "purchase_preference"])
        self.assertEqual([item.value for item in ImportStatus], ["processing", "completed", "failed"])

    def test_valid_product_and_equivalence_json_pass(self):
        product = ProductCreate(
            supplier_id=1,
            raw_name="Grip rojo",
            normalized_name="grip rojo",
            unit_price="12500.00",
            row_hash="a" * 64,
        )
        rule = EquivalenceRuleCreate(
            original_text="Grip rojo de Guerrero y Malusa es el mismo",
            rule_type="equivalence",
            condition_json={
                "type": "equivalence",
                "match": {"name": "grip", "color": "rojo"},
                "suppliers": ["Inversiones Guerrero", "Malusa"],
            },
        )
        self.assertEqual(product.unit_price, Decimal("12500.00"))
        self.assertEqual(rule.condition_json.type, "equivalence")

    def test_all_three_rule_condition_shapes_pass(self):
        examples = (
            (RuleType.EQUIVALENCE, {"type": "equivalence", "match": {"color": "rojo"}, "suppliers": ["A", "B"]}),
            (RuleType.EXCLUSION, {"type": "exclusion", "match": {"color": "azul"}, "suppliers": ["A", "B"]}),
            (RuleType.PURCHASE_PREFERENCE, {"type": "purchase_preference", "match": {"category": "frenos"}, "suppliers": ["A", "B"]}),
        )
        for rule_type, condition in examples:
            with self.subTest(rule_type=rule_type):
                EquivalenceRuleCreate(original_text="Regla estructurada", rule_type=rule_type, condition_json=condition)

    def test_negative_price_fails_with_clear_message(self):
        with self.assertRaises(ValidationError) as context:
            ProductCreate(
                supplier_id=1,
                raw_name="Pastilla",
                normalized_name="pastilla",
                unit_price="-1.00",
                row_hash="b" * 64,
            )
        self.assertIn("El precio unitario no puede ser negativo.", str(context.exception))

    def test_confidence_outside_zero_to_one_fails_with_clear_message(self):
        for confidence in ("-0.001", "1.001"):
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValidationError) as context:
                    ProductLinkCreate(
                        product_id=1,
                        canonical_product_id=2,
                        confidence=confidence,
                        origin="manual",
                    )
                self.assertIn("La confianza debe estar entre 0 y 1.", str(context.exception))

    def test_unknown_rule_type_fails_with_clear_message(self):
        with self.assertRaises(ValidationError) as context:
            EquivalenceRuleCreate(
                original_text="Una regla",
                rule_type="unknown",
                condition_json={"type": "equivalence", "match": {"x": 1}, "suppliers": ["A", "B"]},
            )
        self.assertIn("Tipo de regla desconocido", str(context.exception))

    def test_condition_type_must_match_rule_type(self):
        with self.assertRaises(ValidationError) as context:
            EquivalenceRuleCreate(
                original_text="Una regla",
                rule_type="exclusion",
                condition_json={"type": "equivalence", "match": {"x": 1}, "suppliers": ["A", "B"]},
            )
        self.assertIn("rule_type debe coincidir con condition_json.type.", str(context.exception))


@unittest.skipUnless(
    os.getenv("RUN_MYSQL_INTEGRATION") == "1" and os.getenv("DB_NAME") == "stockmind_test",
    "Activa RUN_MYSQL_INTEGRATION=1 con DB_NAME=stockmind_test para la integración MySQL.",
)
class MySQLTestDatabaseIntegrationTest(unittest.TestCase):
    def test_test_database_has_all_target_tables(self):
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.engine import URL

        from app.core.config import get_settings

        settings = get_settings()
        url = URL.create(
            "mysql+pymysql",
            username=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            query={"charset": "utf8mb4"},
        )
        engine = create_engine(url, pool_pre_ping=True)
        try:
            actual = set(inspect(engine).get_table_names())
            self.assertEqual(actual, set(Base.metadata.tables))
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()