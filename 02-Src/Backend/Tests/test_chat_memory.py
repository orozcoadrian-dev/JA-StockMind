import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from Backend.Agent.core import AgentCore
from Backend.Agent.persistent_memory import PersistentMemory
from Backend.Agent.tools import TOOL_SCHEMAS, execute_tool
from app.core.errors import register_exception_handlers
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
from app.models import (
    AgentAction,
    AgentMemoryFact,
    AgentMemoryFactStatus,
    ChatMessage,
    ChatMessageRole,
    ChatSession,
    ChatSessionStatus,
)
from app.routers.agent_sessions import router as agent_sessions_router
from app.routers.agent_memory import router as agent_memory_router


@compiles(mysql.TINYINT, "sqlite")
def compile_mysql_tinyint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(mysql.LONGTEXT, "sqlite")
def compile_mysql_longtext_for_sqlite(type_, compiler, **kwargs):
    return "TEXT"


def create_test_schema(engine):
    updated_at_default = ChatSession.__table__.c.updated_at.server_default
    fact_updated_at_default = AgentMemoryFact.__table__.c.updated_at.server_default
    ChatSession.__table__.c.updated_at.server_default = text("CURRENT_TIMESTAMP")
    AgentMemoryFact.__table__.c.updated_at.server_default = text("CURRENT_TIMESTAMP")
    try:
        Base.metadata.create_all(
            engine,
            tables=[
                ChatSession.__table__,
                AgentAction.__table__,
                ChatMessage.__table__,
                AgentMemoryFact.__table__,
            ],
        )
    finally:
        ChatSession.__table__.c.updated_at.server_default = updated_at_default
        AgentMemoryFact.__table__.c.updated_at.server_default = fact_updated_at_default


class FailingLLM:
    def complete(self, messages, tools):
        raise RuntimeError("Proveedor de prueba no disponible.")


class RememberFactLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "tool_calls": [
                    {
                        "id": "call-remember",
                        "name": "remember_fact",
                        "arguments": {
                            "key": "supplier_preference",
                            "value": "Comparar precios por proveedor Malusa primero.",
                        },
                    }
                ]
            }
        return {"content": "Guardaré esa preferencia después de tu confirmación.", "tool_calls": []}


class SummarizingLLM:
    def __init__(self):
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        if not tools:
            return {"content": "Resumen: conversación sobre inventario.", "model": "summary-test"}
        return {"content": "Respuesta final.", "model": "chat-test"}


class ChatMemoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        create_test_schema(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.addCleanup(self.engine.dispose)

    def test_create_and_append_messages_tracks_sequence_count_and_last_message_time(self):
        timestamps = [
            datetime(2026, 1, 1, 12, 0, 0) + timedelta(seconds=second)
            for second in range(4)
        ]
        db = self.session_factory()
        try:
            with patch("Backend.Agent.persistent_memory.datetime") as clock:
                clock.now.side_effect = timestamps
                memory = PersistentMemory(db)
                session = memory.create_session()
                memory.append_message(session.external_id, "user", "Pregunta")
                memory.append_message(session.external_id, "assistant", "Llamando herramienta")
                memory.append_message(
                    session.external_id,
                    "tool",
                    '{"ok": true}',
                    tool_name="search_products",
                    tool_call_id="call-1",
                    tool_result={"ok": True},
                )
            db.commit()

            history = memory.get_history(session.external_id)
            db.refresh(session)

            self.assertEqual([message.seq for message in history], [1, 2, 3])
            self.assertEqual(
                [message.role for message in history],
                [ChatMessageRole.USER, ChatMessageRole.ASSISTANT, ChatMessageRole.TOOL],
            )
            self.assertEqual(session.message_count, 3)
            self.assertEqual(session.last_message_at, timestamps[-1])
            self.assertEqual(history[2].tool_call_id, "call-1")
            self.assertEqual(history[2].tool_result, {"ok": True})
        finally:
            db.close()

    def test_history_survives_new_database_session_after_engine_dispose(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'chat-memory.db'}")
            create_test_schema(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            db = factory()
            session = PersistentMemory(db).create_session("Persistente")
            external_id = session.external_id
            PersistentMemory(db).append_message(external_id, "user", "Pregunta guardada")
            PersistentMemory(db).append_message(external_id, "assistant", "Respuesta guardada")
            db.commit()
            db.close()
            engine.dispose()

            restarted_db = factory()
            try:
                history = PersistentMemory(restarted_db).get_history(external_id)
                self.assertEqual(
                    [message.content for message in history],
                    ["Pregunta guardada", "Respuesta guardada"],
                )
                self.assertEqual([message.seq for message in history], [1, 2])
            finally:
                restarted_db.close()
                engine.dispose()

    def test_llm_context_limits_plain_history_and_keeps_tool_call_pairs(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            plain_session = memory.create_session()
            for index in range(5):
                memory.append_message(
                    plain_session.external_id,
                    "user" if index % 2 == 0 else "assistant",
                    f"Mensaje {index + 1}",
                )
            plain_context = memory.get_llm_context(plain_session.external_id, max_messages=2)
            self.assertEqual(
                [(message["role"], message["content"]) for message in plain_context],
                [("assistant", "Mensaje 4"), ("user", "Mensaje 5")],
            )

            tool_session = memory.create_session()
            memory.append_message(tool_session.external_id, "user", "Busca un producto")
            memory.append_message(
                tool_session.external_id,
                "assistant",
                "",
                tool_calls=[
                    {
                        "id": "call-search",
                        "type": "function",
                        "function": {"name": "search_products", "arguments": "{}"},
                    }
                ],
            )
            memory.append_message(
                tool_session.external_id,
                "tool",
                '{"data": []}',
                tool_name="search_products",
                tool_call_id="call-search",
                tool_result={"data": []},
            )
            memory.append_message(tool_session.external_id, "assistant", "Sin resultados.")

            tool_context = memory.get_llm_context(tool_session.external_id, max_messages=2)
            self.assertEqual(
                [message["role"] for message in tool_context],
                ["assistant", "tool", "assistant"],
            )
            for index, message in enumerate(tool_context):
                if message["role"] == "tool":
                    self.assertTrue(
                        any(
                            earlier["role"] == "assistant"
                            and any(
                                call.get("id") == message.get("tool_call_id")
                                for call in earlier.get("tool_calls", [])
                            )
                            for earlier in tool_context[:index]
                        )
                    )
        finally:
            db.close()

    def test_first_user_message_generates_title_limited_to_80_characters(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            first_message = f"Consulta de inventario: {'producto ' * 20}"

            memory.append_message(session.external_id, "user", first_message)
            db.commit()

            self.assertEqual(session.title, first_message[:80])
            self.assertEqual(len(session.title), 80)
        finally:
            db.close()

    def test_summary_threshold_defaults_to_sixty_and_is_configurable(self):
        db = self.session_factory()
        try:
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(PersistentMemory(db).summary_threshold, 60)
            with patch.dict("os.environ", {"AGENT_SUMMARY_THRESHOLD": "12"}):
                self.assertEqual(PersistentMemory(db).summary_threshold, 12)
        finally:
            db.close()

    def test_archiving_preserves_messages_and_history_remains_accessible(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            memory.append_message(session.external_id, "user", "Mensaje antes de archivar")
            db.commit()

            archived = memory.archive_session(session.external_id)
            db.commit()
            history = memory.get_history(session.external_id)
            archived_sessions, total = memory.list_sessions(
                status=ChatSessionStatus.ARCHIVED,
                limit=10,
            )

            self.assertEqual(archived.status, ChatSessionStatus.ARCHIVED)
            self.assertEqual(total, 1)
            self.assertEqual([message.content for message in history], ["Mensaje antes de archivar"])
            self.assertEqual(archived_sessions[0].external_id, session.external_id)
        finally:
            db.close()

    def test_agent_session_endpoints_cover_pagination_messages_updates_export_and_errors(self):
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(agent_sessions_router, prefix="/api/v1")
        register_exception_handlers(app)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        created = [
            client.post("/api/v1/agent/sessions", json={"title": f"Conversación {index}"}).json()["data"]
            for index in range(3)
        ]
        session_id = created[0]["external_id"]

        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            memory.append_message(session_id, "user", "Pregunta de exportación")
            memory.append_message(
                session_id,
                "assistant",
                "Consulta de herramienta",
                tool_calls=[
                    {
                        "id": "call-export",
                        "type": "function",
                        "function": {"name": "search_products", "arguments": "{}"},
                    }
                ],
            )
            memory.append_message(
                session_id,
                "tool",
                '{"data": []}',
                tool_name="search_products",
                tool_call_id="call-export",
                tool_result={"data": []},
            )
            db.commit()
        finally:
            db.close()

        page = client.get("/api/v1/agent/sessions?status=all&limit=1&offset=1")
        detail = client.get(f"/api/v1/agent/sessions/{session_id}")
        messages = client.get(f"/api/v1/agent/sessions/{session_id}/messages")
        renamed = client.patch(
            f"/api/v1/agent/sessions/{session_id}",
            json={"title": "Título actualizado"},
        )
        archived = client.patch(
            f"/api/v1/agent/sessions/{session_id}",
            json={"status": "archived"},
        )
        archived_messages = client.get(f"/api/v1/agent/sessions/{session_id}/messages")
        exported = client.get(f"/api/v1/agent/sessions/{session_id}/export")
        missing = client.get(f"/api/v1/agent/sessions/{uuid4()}")
        invalid_uuid = client.get("/api/v1/agent/sessions/no-es-un-uuid")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["meta"], {"total": 3, "limit": 1, "offset": 1})
        self.assertEqual(len(page.json()["data"]), 1)
        self.assertEqual(detail.json()["data"]["external_id"], session_id)
        self.assertEqual([message["role"] for message in messages.json()["data"]], ["user", "assistant"])
        self.assertEqual(renamed.json()["data"]["title"], "Título actualizado")
        self.assertEqual(archived.json()["data"]["status"], "archived")
        self.assertEqual(len(archived_messages.json()["data"]), 2)
        self.assertEqual(
            [message["role"] for message in exported.json()["data"]["messages"]],
            ["user", "assistant", "tool"],
        )
        self.assertEqual(exported.json()["meta"]["message_count"], 3)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "CHAT_SESSION_NOT_FOUND")
        self.assertEqual(invalid_uuid.status_code, 422)
        self.assertEqual(invalid_uuid.json()["error"]["code"], "VALIDATION_ERROR")

    def test_provider_failure_keeps_user_and_degraded_assistant_messages(self):
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            result = AgentCore(FailingLLM(), self.session_factory).run("Consulta que falla")

        db = self.session_factory()
        try:
            history = PersistentMemory(db).get_history(result["session_id"])
            self.assertEqual(
                [message.role for message in history],
                [ChatMessageRole.USER, ChatMessageRole.ASSISTANT],
            )
            self.assertEqual(history[0].content, "Consulta que falla")
            self.assertIn("no está disponible", history[1].content)
            self.assertEqual(result["message_id"], history[1].id)
        finally:
            db.close()

    def test_destructive_action_confirmation_is_linked_to_session_and_agent_action(self):
        db = self.session_factory()
        try:
            session = PersistentMemory(db).create_session("Confirmación")
            action = AgentAction(
                session_id=session.external_id,
                chat_session_id=session.id,
                tool="consolidate",
                input_params={"suggestion_id": 41},
                result={"summary": "Esperando confirmación."},
                required_confirmation=True,
            )
            db.add(action)
            db.commit()
            action_id = action.id
            external_id = session.external_id
        finally:
            db.close()

        with patch(
            "Backend.Agent.core.execute_tool",
            return_value={"summary": "Consolidación completada."},
        ):
            AgentCore(FailingLLM(), self.session_factory).confirm_action(action_id, True)

        db = self.session_factory()
        try:
            action = db.get(AgentAction, action_id)
            decision = db.scalar(
                select(ChatMessage).where(
                    ChatMessage.session_id == action.chat_session_id,
                    ChatMessage.agent_action_id == action.id,
                )
            )
            self.assertTrue(action.approved)
            self.assertEqual(action.session_id, external_id)
            self.assertEqual(decision.role, ChatMessageRole.USER)
            self.assertEqual(decision.tool_name, "consolidate")
            self.assertEqual(
                decision.tool_result,
                {"approved": True, "action_id": action_id},
            )
            self.assertIn("aprobó", decision.content)
        finally:
            db.close()

    def test_concurrent_appends_receive_distinct_consecutive_sequences(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(
                f"sqlite:///{Path(directory) / 'concurrent-chat.db'}",
                connect_args={"timeout": 10},
            )

            @event.listens_for(engine, "begin")
            def begin_immediate(connection):
                connection.exec_driver_sql("BEGIN IMMEDIATE")

            create_test_schema(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            db = factory()
            session = PersistentMemory(db).create_session()
            external_id = session.external_id
            db.commit()
            db.close()
            barrier = Barrier(2)

            def append_message(content):
                worker_db = factory()
                try:
                    barrier.wait(timeout=5)
                    message = PersistentMemory(worker_db).append_message(
                        external_id,
                        "user",
                        content,
                    )
                    worker_db.commit()
                    return message.seq
                finally:
                    worker_db.close()

            try:
                with ThreadPoolExecutor(max_workers=2) as workers:
                    sequences = list(workers.map(append_message, ["Concurrente A", "Concurrente B"]))

                check_db = factory()
                try:
                    history = PersistentMemory(check_db).get_history(external_id)
                    self.assertEqual(sorted(sequences), [1, 2])
                    self.assertEqual([message.seq for message in history], [1, 2])
                    self.assertEqual(
                        {message.content for message in history},
                        {"Concurrente A", "Concurrente B"},
                    )
                finally:
                    check_db.close()
            finally:
                engine.dispose()

    def test_confirmed_remember_fact_is_linked_to_the_originating_session_and_message(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            db.commit()
            external_id = session.external_id
        finally:
            db.close()

        llm = RememberFactLLM()
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            result = AgentCore(llm, self.session_factory).run(
                "Recuerda que prefiero comparar precios por proveedor Malusa primero.",
                external_id,
            )

        self.assertIn("remember_fact", TOOL_SCHEMAS)
        self.assertEqual(
            TOOL_SCHEMAS["remember_fact"]["parameters"]["properties"]["key"]["type"],
            "string",
        )
        self.assertEqual(len(result["pending_confirmations"]), 1)
        action_id = result["pending_confirmations"][0]["action_id"]

        db = self.session_factory()
        try:
            self.assertEqual(db.query(AgentMemoryFact).count(), 0)
            action = db.get(AgentAction, action_id)
            source_message_id = action.result["_source_message_id"]
            user_message = (
                db.query(ChatMessage)
                .filter_by(session_id=action.chat_session_id, role=ChatMessageRole.USER)
                .order_by(ChatMessage.seq.asc())
                .first()
            )
            self.assertTrue(action.required_confirmation)
            self.assertEqual(source_message_id, user_message.id)
        finally:
            db.close()

        confirmation_result = AgentCore(FailingLLM(), self.session_factory).confirm_action(
            action_id,
            True,
        )
        self.assertNotIn("error", confirmation_result)
        self.assertEqual(confirmation_result["data"]["source_message_id"], source_message_id)

        db = self.session_factory()
        try:
            fact = db.query(AgentMemoryFact).one()
            session = db.query(ChatSession).filter_by(external_id=external_id).one()
            self.assertEqual(fact.key, "supplier_preference")
            self.assertEqual(fact.value, "Comparar precios por proveedor Malusa primero.")
            self.assertEqual(fact.status, AgentMemoryFactStatus.ACTIVE)
            self.assertEqual(fact.source_session_id, session.id)
            self.assertEqual(fact.source_message_id, source_message_id)

            listed = execute_tool("list_memory_facts", {}, db=db)
            self.assertEqual(listed["data"][0]["id"], fact.id)
            self.assertEqual(listed["data"][0]["key"], fact.key)
        finally:
            db.close()

    def test_active_facts_are_compact_and_capped_at_twenty_in_llm_context(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            source_message = memory.append_message(session.external_id, "user", "Hola")
            facts = [
                memory.create_memory_fact(
                    key=f"preference-{index}",
                    value="x" * 600 if index == 21 else f"Preferencia {index}",
                    source_session_id=session.id,
                    source_message_id=source_message.id,
                )
                for index in range(22)
            ]
            memory.disable_memory_fact(facts[0].id)
            db.commit()

            context = memory.get_llm_context(session.external_id, max_messages=1)
            facts_block = next(item["content"] for item in context if item["role"] == "system")
            fact_lines = [line for line in facts_block.splitlines() if line.startswith("- ")]

            self.assertEqual(len(fact_lines), 20)
            self.assertNotIn('"preference-0"', facts_block)
            self.assertNotIn('"preference-1"', facts_block)
            self.assertIn("x" * 497 + "...", facts_block)
            self.assertIn("datos no confiables", facts_block)
            self.assertEqual(context[-1]["role"], "user")
        finally:
            db.close()

    def test_summary_boundary_keeps_tool_call_and_result_together_in_llm_context(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db, max_messages=4, summary_threshold=3)
            session = memory.create_session()
            memory.append_message(session.external_id, "user", "Mensaje antiguo 1")
            memory.append_message(session.external_id, "assistant", "Respuesta antigua")
            memory.append_message(session.external_id, "user", "Mensaje antiguo 2")
            memory.append_message(
                session.external_id,
                "assistant",
                "",
                tool_calls=[
                    {
                        "id": "call-summary",
                        "type": "function",
                        "function": {"name": "search_products", "arguments": "{}"},
                    }
                ],
            )
            memory.append_message(
                session.external_id,
                "tool",
                '{"data": []}',
                tool_name="search_products",
                tool_call_id="call-summary",
                tool_result={"data": []},
            )
            memory.append_message(session.external_id, "assistant", "No hay resultados.")
            candidate = memory.get_summary_candidate(session.external_id)
            self.assertIsNotNone(candidate)
            _, _, through_seq = candidate
            self.assertEqual(through_seq, 3)

            memory.append_message(
                session.external_id,
                "system",
                "Resumen de mensajes antiguos.",
                tool_name=PersistentMemory.SUMMARY_TOOL_NAME,
                tool_result={"summary_through_seq": through_seq},
            )
            db.commit()
            context = memory.get_llm_context(session.external_id, max_messages=2)

            self.assertEqual([message["role"] for message in context], [
                "system",
                "assistant",
                "tool",
                "assistant",
            ])
            self.assertEqual(context[2]["tool_call_id"], "call-summary")
            self.assertEqual(
                context[1]["tool_calls"][0]["id"],
                context[2]["tool_call_id"],
            )
        finally:
            db.close()

    def test_long_conversation_is_summarized_for_context_without_deleting_source_messages(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            for index in range(1, 6):
                memory.append_message(
                    session.external_id,
                    "user" if index % 2 else "assistant",
                    f"Mensaje {index}",
                )
            db.commit()
            external_id = session.external_id
            original_ids = [message.id for message in memory.get_history(external_id)]
        finally:
            db.close()

        llm = SummarizingLLM()
        with (
            patch.dict(
                "os.environ",
                {"AGENT_SUMMARY_THRESHOLD": "4", "AGENT_MEMORY_MAX_MESSAGES": "4"},
            ),
            patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"),
        ):
            AgentCore(llm, self.session_factory).run("Mensaje 6", external_id)

        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            history = memory.get_history(external_id)
            summary = next(
                message
                for message in history
                if message.role == ChatMessageRole.SYSTEM
                and message.tool_name == PersistentMemory.SUMMARY_TOOL_NAME
            )
            self.assertTrue(set(original_ids).issubset({message.id for message in history}))
            self.assertEqual(summary.tool_result["summary_through_seq"], 4)
            self.assertEqual(summary.content, "Resumen: conversación sobre inventario.")
            self.assertEqual(len(history), 8)

            context = memory.get_llm_context(external_id, max_messages=4)
            self.assertEqual(context[0]["role"], "system")
            self.assertIn("Resumen:", context[0]["content"])
            self.assertIn("dato no confiable", context[0]["content"])
            self.assertFalse(any("Mensaje 1" in item.get("content", "") for item in context))
            self.assertTrue(any("Mensaje 5" in item.get("content", "") for item in context))
            main_request = llm.calls[-1][0]
            self.assertFalse(any("Mensaje 1" in item.get("content", "") for item in main_request))
            self.assertTrue(any("Resumen:" in item.get("content", "") for item in main_request))
        finally:
            db.close()

    def test_summary_failure_keeps_original_messages_and_returns_a_warning(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            for index in range(5):
                memory.append_message(
                    session.external_id,
                    "user" if index % 2 == 0 else "assistant",
                    f"Original {index}",
                )
            db.commit()
            external_id = session.external_id
        finally:
            db.close()

        with (
            patch.dict("os.environ", {"AGENT_SUMMARY_THRESHOLD": "3"}),
            patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"),
        ):
            result = AgentCore(FailingLLM(), self.session_factory).run("Siguiente", external_id)

        db = self.session_factory()
        try:
            history = PersistentMemory(db).get_history(external_id)
            self.assertIn("No se pudo generar o guardar el resumen", result["warning"])
            self.assertTrue(all(f"Original {index}" in [item.content for item in history] for index in range(5)))
            self.assertFalse(any(item.tool_name == PersistentMemory.SUMMARY_TOOL_NAME for item in history))
        finally:
            db.close()

    def test_memory_fact_endpoints_list_and_disable_without_deleting(self):
        db = self.session_factory()
        try:
            memory = PersistentMemory(db)
            session = memory.create_session()
            source_message = memory.append_message(session.external_id, "user", "Prefiero proveedor Malusa.")
            active_fact = memory.create_memory_fact(
                "supplier", "Malusa primero", session.id, source_message.id
            )
            disabled_fact = memory.create_memory_fact(
                "format", "Precios comparados", session.id, source_message.id
            )
            memory.disable_memory_fact(disabled_fact.id)
            db.commit()
            fact_id = active_fact.id
        finally:
            db.close()

        app = FastAPI()
        app.include_router(agent_memory_router, prefix="/api/v1")
        register_exception_handlers(app)

        def override_get_db():
            connection = self.session_factory()
            try:
                yield connection
            finally:
                connection.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        active = client.get("/api/v1/agent/memory/facts")
        disabled = client.get("/api/v1/agent/memory/facts?status=all&limit=1&offset=1")
        changed = client.patch(
            f"/api/v1/agent/memory/facts/{fact_id}",
            json={"status": "disabled"},
        )
        missing = client.patch(
            "/api/v1/agent/memory/facts/99999",
            json={"status": "disabled"},
        )
        delete_response = client.delete(f"/api/v1/agent/memory/facts/{fact_id}")

        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["meta"]["total"], 1)
        self.assertEqual(active.json()["data"][0]["status"], "active")
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()["meta"], {"total": 2, "limit": 1, "offset": 1})
        self.assertEqual(changed.json()["data"]["status"], "disabled")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "HTTP_404")
        self.assertEqual(delete_response.status_code, 405)

        db = self.session_factory()
        try:
            self.assertEqual(db.query(AgentMemoryFact).count(), 2)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
