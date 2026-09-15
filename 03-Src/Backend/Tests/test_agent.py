import unittest
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from Backend.Agent.core import AgentCore
from Backend.Agent.memory import ConversationMemory
from Backend.Agent.tools import TOOL_SCHEMAS, execute_tool
from Backend.Models.equivalence_rule import EquivalenceRule
from Backend.Models.canonical_product import CanonicalProduct
from Backend.Models.product import Product
from Backend.Models.product_link import ProductLink
from Backend.Models.supplier import Supplier
from Backend.database import Base


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "tool_calls": [{
                    "id": "call-1",
                    "name": "search_products",
                    "arguments": {"query": "grip rojo"},
                }]
            }
        return {"content": "Encontré los productos y dejé la decisión lista para revisión."}


class AgentWorkflowTest(unittest.TestCase):
    def test_tool_schemas_and_loop_chain_tool_calls(self):
        self.assertIn("search_products", TOOL_SCHEMAS)
        self.assertIn("consolidate", TOOL_SCHEMAS)

        core = AgentCore(llm_client=FakeLLM())
        result = core.run("Busca los grips rojos", session_id="test-agent")

        self.assertEqual(result["response"], "Encontré los productos y dejé la decisión lista para revisión.")
        self.assertEqual(result["tools_used"], ["search_products"])

    def test_consolidation_requires_confirmation(self):
        result = execute_tool("consolidate", {"product_ids": [1, 2], "canonical_name": "Grip rojo"})

        self.assertTrue(result["confirmation_required"])
        self.assertIn("confirmación", result["summary"].lower())

    def test_memory_summarizes_old_messages(self):
        memory = ConversationMemory(max_messages=3)
        for index in range(5):
            memory.add("user", f"mensaje {index}")

        messages = memory.messages()
        self.assertLessEqual(len(messages), 4)
        self.assertTrue(any(message["role"] == "system" for message in messages))

    def test_confirmed_rule_is_persisted_and_applied_retroactively(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        guerrero = Supplier(name="Inversiones Guerrero", nit="agent-1")
        malusa = Supplier(name="Malusa", nit="agent-2")
        session.add_all([guerrero, malusa])
        session.flush()
        session.add_all([
            Product(supplier_id=guerrero.id, provider_code="G-1", raw_name="GRIP ROJO 22mm", normalized_name="grip rojo 22mm", category="manillar", unit_price=185000, currency="COP", unit_of_measure="unidad", pack_quantity=1, price_list_date=date(2026, 9, 1), row_hash="agent-g1"),
            Product(supplier_id=malusa.id, provider_code="M-1", raw_name="Manubrio grip rojo 22mm", normalized_name="manubrio grip rojo 22mm", category="manillar", unit_price=190000, currency="COP", unit_of_measure="unidad", pack_quantity=1, price_list_date=date(2026, 9, 1), row_hash="agent-m1"),
        ])
        session.commit()

        result = execute_tool("create_equivalence_rule", {"natural_text": "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo"}, db=session, confirmed=True)

        self.assertEqual(session.scalar(select(func.count(EquivalenceRule.id))), 1)
        self.assertEqual(session.scalar(select(func.count(ProductLink.id))), 2)
        self.assertEqual(result["data"]["affected_pairs"], 1)
        session.close()

    def test_read_only_tools_return_structured_real_data(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        supplier = Supplier(name="Malusa", nit="tools-1")
        session.add(supplier)
        session.flush()
        product = Product(supplier_id=supplier.id, provider_code="M-1", raw_name="Freno delantero", normalized_name="freno delantero", category="frenos", unit_price=86000, currency="COP", unit_of_measure="unidad", pack_quantity=1, price_list_date=date(2026, 9, 1), row_hash="tools-product")
        canonical = CanonicalProduct(name="Freno delantero", category="frenos", attributes={"type": "freno"}, stock_in_bodega=0, minimum_stock=4)
        session.add_all([product, canonical])
        session.flush()
        session.add(ProductLink(product_id=product.id, canonical_product_id=canonical.id, confidence=1.0, origin="test"))
        session.commit()

        self.assertEqual(execute_tool("search_products", {"query": "freno", "supplier_id": supplier.id, "category": "frenos"}, db=session)["data"][0]["id"], product.id)
        self.assertEqual(execute_tool("get_canonical_product", {"id": canonical.id}, db=session)["data"]["id"], canonical.id)
        self.assertIn("data", execute_tool("list_rules", {}, db=session))
        self.assertIn("summary", execute_tool("suggest_matches", {}, db=session))
        self.assertEqual(execute_tool("get_inventory_report", {"filters": {"category": "frenos"}}, db=session)["data"]["total_canonical"], 1)
        self.assertEqual(execute_tool("compare_supplier_prices", {"id": canonical.id}, db=session)["data"][0]["unit_price"], 86000)
        self.assertEqual(execute_tool("get_purchase_suggestions", {"budget": 100000, "categories": ["frenos"]}, db=session)["data"][0]["units_to_buy"], 4)
        self.assertIn("error", execute_tool("search_products", {"query": ""}, db=session))
        self.assertIn("error", execute_tool("unknown_tool", {}, db=session))
        session.close()


if __name__ == "__main__":
    unittest.main()