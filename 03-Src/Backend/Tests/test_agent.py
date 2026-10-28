import unittest
from unittest.mock import Mock, patch

from Backend.Agent.core import AgentCore, GeminiClient
from Backend.Agent.memory import ConversationMemory
from Backend.Agent.tools import TOOL_SCHEMAS, execute_tool


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


class DirectReplyLLM:
    def complete(self, messages, tools):
        return {"content": "Hola. Puedo ayudarte con consultas generales aunque aún no hayas importado productos."}


class FailsOnceLLM:
    def __init__(self):
        self.calls = 0
        self.retry_messages = []

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Fallo temporal del proveedor.")
        self.retry_messages = messages
        return {"content": "El agente volvió a responder."}


class SignatureLLM:
    def __init__(self):
        self.calls = 0
        self.second_turn = []

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "tool_calls": [{
                    "id": "call-search",
                    "name": "search_products",
                    "arguments": {"query": "grip rojo"},
                    "extra_content": {"google": {"thought_signature": "signature-value"}},
                }]
            }
        self.second_turn = messages
        return {"content": "Comparación completada."}


class ParallelToolsLLM:
    def __init__(self):
        self.calls = 0
        self.final_messages = []

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "tool_calls": [
                    {
                        "id": "call-inventory",
                        "name": "search_products",
                        "arguments": {"query": "grip rojo"},
                        "extra_content": {"google": {"thought_signature": "signature-1"}},
                    },
                    {
                        "id": "call-purchases",
                        "name": "search_products",
                        "arguments": {"query": "freno delantero"},
                        "extra_content": {"google": {"thought_signature": "signature-2"}},
                    },
                ]
            }
        self.final_messages = messages
        return {"content": "Reporte preparado."}


class AgentWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.scalars.return_value.all.return_value = []

    def test_gemini_client_uses_free_model_by_default(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True):
            client = GeminiClient()

        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.model, "gemini-3.5-flash-lite")
        self.assertEqual(
            client.base_url,
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )

    def test_tool_schemas_and_loop_chain_tool_calls(self):
        self.assertIn("search_products", TOOL_SCHEMAS)
        self.assertIn("consolidate", TOOL_SCHEMAS)

        with patch(
            "Backend.Agent.tools.list_products",
            return_value=([{"id": 1, "raw_name": "Grip rojo"}], {"total": 1}),
        ) as search:
            core = AgentCore(llm_client=FakeLLM(), db_factory=lambda: self.db)
            result = core.run("Busca los grips rojos", session_id="test-agent")

        search.assert_called_once()
        self.assertIn("search_products", TOOL_SCHEMAS)
        self.assertIn("list_pending_matches", TOOL_SCHEMAS)
        self.assertIn("consolidate", TOOL_SCHEMAS)
        self.assertEqual(result["response"], "Encontré los productos y dejé la decisión lista para revisión.")
        self.assertEqual(result["tools_used"], ["search_products"])

    def test_gemini_thought_signature_is_preserved_across_tool_turns(self):
        llm = SignatureLLM()
        with patch("Backend.Agent.tools.list_products", return_value=([], {"total": 0})):
            core = AgentCore(llm_client=llm, db_factory=lambda: self.db)
            result = core.run("Busca grip rojo", session_id="signature-session")

        self.assertEqual(result["response"], "Comparación completada.")
        assistant_message = next(message for message in llm.second_turn if message.get("role") == "assistant")
        self.assertEqual(
            assistant_message["tool_calls"][0]["extra_content"]["google"]["thought_signature"],
            "signature-value",
        )

    def test_multiple_tool_calls_are_returned_in_one_assistant_message(self):
        llm = ParallelToolsLLM()
        with patch("Backend.Agent.tools.list_products", return_value=([], {"total": 0})):
            core = AgentCore(llm_client=llm, db_factory=lambda: self.db)
            result = core.run("Prepara reporte de productos y compras", session_id="multi-tool-session")

        assistant_messages = [message for message in llm.final_messages if message.get("role") == "assistant"]
        self.assertEqual(result["response"], "Reporte preparado.")
        self.assertEqual(len(assistant_messages), 1)
        calls = assistant_messages[0]["tool_calls"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            [call["extra_content"]["google"]["thought_signature"] for call in calls],
            ["signature-1", "signature-2"],
        )
    def test_chat_answers_without_imported_csv_or_tool_calls(self):
        core = AgentCore(llm_client=DirectReplyLLM(), db_factory=lambda: self.db)

        result = core.run("Hola, ¿qué puedes hacer?", session_id="empty-catalog")

        self.assertIn("Puedo ayudarte", result["response"])
        self.assertEqual(result["tools_used"], [])
        self.assertEqual(result["pending_confirmations"], [])

    def test_failed_provider_request_does_not_poison_session_memory(self):
        llm = FailsOnceLLM()
        core = AgentCore(llm_client=llm, db_factory=lambda: self.db)

        with self.assertRaises(RuntimeError):
            core.run("Primer intento", session_id="retry-session")

        result = core.run("Segundo intento", session_id="retry-session")

        self.assertEqual(result["response"], "El agente volvió a responder.")
        self.assertEqual(
            [message["content"] for message in llm.retry_messages if message["role"] == "user"],
            ["Segundo intento"],
        )

    def test_consolidation_requires_confirmation(self):
        result = execute_tool("consolidate", {"suggestion_id": 4, "candidate_product_id": 9})

        self.assertTrue(result["confirmation_required"])
        self.assertIn("confirmación", result["summary"].lower())

    def test_memory_summarizes_old_messages(self):
        memory = ConversationMemory(max_messages=3)
        for index in range(5):
            memory.add("user", f"mensaje {index}")

        messages = memory.messages()
        self.assertLessEqual(len(messages), 4)
        self.assertTrue(any(message["role"] == "system" for message in messages))

    def test_confirmed_rule_uses_live_suppliers_and_recalculates_matches(self):
        query_results = iter((
            ["Inversiones Guerrero", "Malusa"],
            ["Accesorios"],
        ))
        self.db.scalars.side_effect = lambda statement: Mock(all=lambda: next(query_results))

        with (
            patch("Backend.Agent.tools.create_rule", return_value={"id": 3, "original_text": "regla"}) as save_rule,
            patch("Backend.Agent.tools.suggest_matches", return_value=[{"score": 1.0}]) as recalculate,
        ):
            result = execute_tool(
                "create_equivalence_rule",
                {"natural_text": "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo"},
                db=self.db,
                confirmed=True,
            )

        self.assertEqual(result["data"]["recalculated_suggestions"], 1)
        saved = save_rule.call_args.args[1]
        self.assertEqual(saved["structured_condition"]["suppliers"], ["Inversiones Guerrero", "Malusa"])
        self.assertEqual(saved["structured_condition"]["match"]["attributes"]["color"], "rojo")
        recalculate.assert_called_once_with(self.db)

    def test_read_tools_delegate_to_mysql_catalog_services(self):
        with (
            patch("Backend.Agent.tools.list_products", return_value=([{"id": 1}], {"total": 1})) as search,
            patch("Backend.Agent.tools.get_canonical_product", return_value={"id": 8}) as canonical,
            patch("Backend.Agent.tools.suggest_matches", return_value=[{"score": 0.9}]) as matches,
            patch("Backend.Agent.tools.list_pending_matches", return_value=([{"id": 5}], {"total": 1})) as pending,
            patch("Backend.Agent.tools.list_rules", return_value=([{"id": 2}], {"total": 1})) as rules,
            patch("Backend.Agent.tools.inventory_report", return_value={"total_canonical": 1, "low_stock": [], "without_minimum_count": 0}) as inventory,
            patch("Backend.Agent.tools.price_comparison", return_value=[{"unit_price": 86000}]) as prices,
            patch("Backend.Agent.tools.purchase_suggestions", return_value=[{"units_to_buy": 4}]) as purchases,
        ):
            self.assertEqual(execute_tool("search_products", {"query": "freno"}, db=self.db)["data"], [{"id": 1}])
            self.assertEqual(execute_tool("get_canonical_product", {"id": 8}, db=self.db)["data"]["id"], 8)
            self.assertEqual(execute_tool("suggest_matches", {"import_id": 17}, db=self.db)["data"][0]["score"], 0.9)
            self.assertEqual(execute_tool("list_pending_matches", {}, db=self.db)["data"][0]["id"], 5)
            self.assertEqual(execute_tool("list_rules", {}, db=self.db)["data"][0]["id"], 2)
            self.assertEqual(execute_tool("get_inventory_report", {}, db=self.db)["data"]["total_canonical"], 1)
            self.assertEqual(execute_tool("compare_supplier_prices", {"canonical_product_id": 8}, db=self.db)["data"][0]["unit_price"], 86000)
            self.assertEqual(execute_tool("get_purchase_suggestions", {}, db=self.db)["data"][0]["units_to_buy"], 4)

        search.assert_called_once()
        canonical.assert_called_once_with(self.db, 8)
        matches.assert_called_once_with(self.db, import_id=17)
        pending.assert_called_once_with(self.db, 1, 100)
        rules.assert_called_once_with(self.db, 1, 100)
        inventory.assert_called_once_with(self.db, None)
        prices.assert_called_once_with(self.db, 8)
        purchases.assert_called_once()

    def test_price_comparison_by_product_name_includes_supplier_names(self):
        self.db.scalars.return_value.all.return_value = [
            type("SupplierRow", (), {"id": 1, "name": "Malusa"})(),
            type("SupplierRow", (), {"id": 2, "name": "Guerrero"})(),
        ]
        products = [
            {"id": 1, "supplier_id": 1, "unit_price": 86000},
            {"id": 2, "supplier_id": 2, "unit_price": 91000},
        ]

        with patch("Backend.Agent.tools.list_products", return_value=(products, {"total": 2})) as search:
            result = execute_tool("compare_supplier_prices", {"query": "grip rojo"}, db=self.db)

        self.assertEqual([item["supplier_name"] for item in result["data"]], ["Malusa", "Guerrero"])
        self.assertIn("no prueban", result["summary"])
        search.assert_called_once_with(self.db, 1, 100, "grip rojo", None, None, "price")

    def test_price_comparison_without_catalog_data_gives_next_step(self):
        with patch("Backend.Agent.tools.list_products", return_value=([], {"total": 0})):
            result = execute_tool("compare_supplier_prices", {"query": "repuesto desconocido"}, db=self.db)

        self.assertEqual(result["data"], [])
        self.assertIn("Importa la lista", result["summary"])

    def test_purchase_report_explains_unconfigured_stock_minimums(self):
        with (
            patch("Backend.Agent.tools.purchase_suggestions", return_value=[]),
            patch("Backend.Agent.tools.inventory_report", return_value={"total_canonical": 34, "low_stock": [], "without_minimum_count": 34}),
        ):
            result = execute_tool("get_purchase_suggestions", {}, db=self.db)

        self.assertEqual(result["data"], [])
        self.assertIn("configura el stock mínimo", result["summary"])
        self.assertIn("34", result["summary"])


if __name__ == "__main__":
    unittest.main()