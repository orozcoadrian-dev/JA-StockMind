import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Agent.core import AgentCore
from Backend.Agent.persistent_memory import PersistentMemory, SessionNotFoundError
from app.db.base import Base
from app.core.errors import register_exception_handlers
from app.models import AgentAction, ChatMessage, ChatMessageRole, ChatSession, ChatSessionStatus


@compiles(mysql.TINYINT, "sqlite")
def compile_mysql_tinyint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(mysql.LONGTEXT, "sqlite")
def compile_mysql_longtext_for_sqlite(type_, compiler, **kwargs):
    return "TEXT"


class ReplyLLM:
    model = "test-chat-model"

    def __init__(self, content):
        self.content = content
        self.messages = None

    def complete(self, messages, tools):
        self.messages = messages
        return {"content": self.content, "tool_calls": [], "usage": {"prompt_tokens": 12, "completion_tokens": 4}}


class ToolThenReplyLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "tool_calls": [
                    {"id": "call-1", "name": "search_products", "arguments": {}}
                ]
            }
        return {"content": "Respuesta final."}


class FailsLLM:
    def complete(self, messages, tools):
        raise RuntimeError("Credenciales del proveedor no configuradas.")


class UserPersistenceCheckLLM:
    def __init__(self, session_factory, external_id):
        self.session_factory = session_factory
        self.external_id = external_id

    def complete(self, messages, tools):
        db = self.session_factory()
        history = db.scalars(
            select(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(ChatSession.external_id == self.external_id)
            .order_by(ChatMessage.seq)
        ).all()
        db.close()
        if not history or history[0].role != ChatMessageRole.USER:
            raise AssertionError("El mensaje del usuario no se había confirmado antes de llamar al LLM.")
        return {"content": "Respuesta después de persistir al usuario."}


class ChatPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        updated_at_default = ChatSession.__table__.c.updated_at.server_default
        ChatSession.__table__.c.updated_at.server_default = text("CURRENT_TIMESTAMP")
        try:
            Base.metadata.create_all(
                self.engine,
                tables=[
                    ChatSession.__table__,
                    ChatMessage.__table__,
                    Base.metadata.tables["agent_actions"],
                ],
            )
        finally:
            ChatSession.__table__.c.updated_at.server_default = updated_at_default
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.engine.dispose()

    def test_conversation_history_is_loaded_from_database_between_agent_instances(self):
        db = self.session_factory()
        external_id = PersistentMemory(db).create_session().external_id
        db.commit()
        db.close()
        first_llm = ReplyLLM("Respuesta inicial.")
        next_llm = ReplyLLM("Respuesta siguiente.")
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            first_result = AgentCore(first_llm, self.session_factory).run("Consulta inicial", external_id)
            next_result = AgentCore(next_llm, self.session_factory).run("Consulta siguiente", external_id)

        db = self.session_factory()
        stored_session = db.scalar(select(ChatSession).where(ChatSession.external_id == external_id))
        stored_messages = db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == stored_session.id).order_by(ChatMessage.seq)
        ).all()
        historic_user_messages = [
            item["content"] for item in next_llm.messages if item["role"] == "user"
        ]

        self.assertEqual(first_result["session_id"], external_id)
        self.assertEqual(next_result["session_id"], external_id)
        self.assertEqual(stored_session.title, "Consulta inicial")
        self.assertEqual(stored_session.message_count, 4)
        self.assertEqual([item.seq for item in stored_messages], [1, 2, 3, 4])
        self.assertEqual(historic_user_messages, ["Consulta inicial", "Consulta siguiente"])
        self.assertEqual(stored_messages[1].model, "test-chat-model")
        self.assertEqual(stored_messages[1].tokens_input, 12)
        db.close()

    def test_missing_session_id_generates_public_uuid4(self):
        llm = ReplyLLM("Respuesta.")
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            result = AgentCore(llm, self.session_factory).run("Inicia conversación")

        self.assertEqual(UUID(result["session_id"]).version, 4)

    def test_existing_unknown_session_is_rejected_before_provider_call(self):
        llm = ReplyLLM("No debe usarse.")
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            with self.assertRaises(SessionNotFoundError):
                AgentCore(llm, self.session_factory).run("Pregunta", "missing-session")

        self.assertIsNone(llm.messages)

    def test_user_message_is_committed_before_provider_call(self):
        external_id = str(uuid4())
        db = self.session_factory()
        session = PersistentMemory(db).create_session()
        session.external_id = external_id
        db.commit()
        db.close()
        llm = UserPersistenceCheckLLM(self.session_factory, external_id)

        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            result = AgentCore(llm, self.session_factory).run("Consulta guardada", external_id)

        self.assertEqual(result["response"], "Respuesta después de persistir al usuario.")
        self.assertIsNotNone(result["message_id"])

    def test_provider_failure_is_persisted_and_returned_with_assistant_message_id(self):
        with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
            result = AgentCore(FailsLLM(), self.session_factory).run("Pregunta al agente")

        db = self.session_factory()
        assistant = db.get(ChatMessage, result["message_id"])
        self.assertEqual(result["message_id"], assistant.id)
        self.assertIn("no está disponible", result["content"])
        self.assertEqual(assistant.role, ChatMessageRole.ASSISTANT)
        self.assertIn("no configuradas", assistant.content)
        db.close()

    def test_persistent_memory_manages_sessions_history_and_tool_context(self):
        db = self.session_factory()
        memory = PersistentMemory(db, max_messages=3)
        session = memory.create_session()
        assistant_calls = [
            {
                "id": "call-search",
                "type": "function",
                "function": {"name": "search_products", "arguments": "{}"},
            }
        ]

        user_message = memory.append_message(session.external_id, "user", "Consulta del inventario")
        memory.append_message(
            session.external_id,
            "assistant",
            "",
            tool_calls=assistant_calls,
        )
        memory.append_message(
            session.external_id,
            "tool",
            '{"data": []}',
            tool_name="search_products",
            tool_call_id="call-search",
            tool_result={"data": []},
        )
        memory.append_message(session.external_id, "assistant", "No hay resultados.")

        history = memory.get_history(session.external_id, limit=2)
        context = memory.get_llm_context(session.external_id, max_messages=2)
        sessions, total = memory.list_sessions(limit=10, offset=0)

        self.assertEqual(user_message.seq, 1)
        self.assertEqual(session.title, "Consulta del inventario")
        self.assertEqual(session.message_count, 4)
        self.assertEqual([item.seq for item in history], [3, 4])
        self.assertEqual(
            [(item["role"], item.get("tool_call_id")) for item in context],
            [("assistant", None), ("tool", "call-search"), ("assistant", None)],
        )
        self.assertEqual((sessions[0].external_id, total), (session.external_id, 1))

        renamed = memory.rename_session(session.external_id, "  Título cambiado  ")
        archived = memory.archive_session(session.external_id)
        archived_sessions, archived_total = memory.list_sessions(
            status=ChatSessionStatus.ARCHIVED,
            limit=10,
            offset=0,
        )
        self.assertEqual(renamed.title, "Título cambiado")
        self.assertEqual(archived.status, ChatSessionStatus.ARCHIVED)
        self.assertEqual(archived_total, 1)
        self.assertEqual(archived_sessions[0].id, session.id)
        db.close()

    def test_missing_session_raises_domain_exception(self):
        db = self.session_factory()
        memory = PersistentMemory(db)

        with self.assertRaisesRegex(SessionNotFoundError, "no existe"):
            memory.get_history("missing-session")
        with self.assertRaises(SessionNotFoundError):
            memory.append_message("missing-session", ChatMessageRole.USER, "Hola")
        db.close()

    def test_api_maps_missing_chat_session_to_standard_404_error(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/missing-session")
        def missing_session():
            raise SessionNotFoundError("missing-session")

        response = TestClient(app).get("/missing-session")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "CHAT_SESSION_NOT_FOUND")

    def test_database_commit_failure_returns_response_with_warning(self):
        def fail_commit(*args, **kwargs):
            raise SQLAlchemyError("database unavailable")

        event.listen(Session, "before_commit", fail_commit)
        try:
            llm = ReplyLLM("La respuesta debe llegar al usuario.")
            with patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"):
                result = AgentCore(llm, self.session_factory).run("Pregunta")
        finally:
            event.remove(Session, "before_commit", fail_commit)

        self.assertEqual(result["response"], "La respuesta debe llegar al usuario.")
        self.assertIn("no se pudo guardar", result["warning"])

    def test_action_persistence_failure_does_not_drop_generated_response(self):
        def fail_action_flush(session, flush_context, instances):
            if any(isinstance(item, AgentAction) for item in session.new):
                raise SQLAlchemyError("database unavailable")

        event.listen(Session, "before_flush", fail_action_flush)
        try:
            llm = ToolThenReplyLLM()
            with (
                patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"),
                patch(
                    "Backend.Agent.core.execute_tool",
                    return_value={"summary": "Búsqueda completada.", "data": []},
                ),
            ):
                result = AgentCore(llm, self.session_factory).run("Busca un producto")
        finally:
            event.remove(Session, "before_flush", fail_action_flush)

        self.assertEqual(result["response"], "Respuesta final.")
        self.assertIn("no se pudo guardar", result["warning"])

    def test_confirm_action_appends_user_decision_to_original_session(self):
        db = self.session_factory()
        session = PersistentMemory(db).create_session()
        action = AgentAction(
            session_id=session.external_id,
            chat_session_id=session.id,
            tool="consolidate",
            input_params={"suggestion_id": 1},
            result={"summary": "Esperando confirmación."},
            required_confirmation=True,
        )
        db.add(action)
        db.commit()
        action_id = action.id
        db.close()

        with patch(
            "Backend.Agent.core.execute_tool",
            return_value={"summary": "Consolidación completada."},
        ):
            result = AgentCore(ReplyLLM("Unused"), self.session_factory).confirm_action(action_id, True)

        db = self.session_factory()
        decision = db.scalar(
            select(ChatMessage).where(
                ChatMessage.session_id == session.id,
                ChatMessage.role == ChatMessageRole.USER,
            )
        )
        self.assertEqual(result["summary"], "Consolidación completada.")
        self.assertIn("aprobó", decision.content)
        self.assertIn("consolidate", decision.content)
        self.assertEqual(decision.tool_result, {"approved": True, "action_id": action_id})
        db.close()

    def test_agent_tool_iteration_persists_call_result_action_and_final_message(self):
        llm = ToolThenReplyLLM()
        with (
            patch("Backend.Agent.core.build_system_prompt", return_value="system prompt"),
            patch(
                "Backend.Agent.core.execute_tool",
                return_value={"summary": "Búsqueda completada.", "data": []},
            ),
        ):
            result = AgentCore(llm, self.session_factory).run("Busca un producto")

        db = self.session_factory()
        session = db.scalar(
            select(ChatSession).where(ChatSession.external_id == result["session_id"])
        )
        history = db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.seq)
        ).all()
        action = db.scalar(select(AgentAction).where(AgentAction.chat_session_id == session.id))

        self.assertEqual([item.role for item in history], [
            ChatMessageRole.USER,
            ChatMessageRole.ASSISTANT,
            ChatMessageRole.TOOL,
            ChatMessageRole.ASSISTANT,
        ])
        self.assertEqual(history[1].tool_calls[0]["id"], "call-1")
        self.assertEqual(history[2].tool_name, "search_products")
        self.assertEqual(history[2].tool_call_id, "call-1")
        self.assertEqual(history[2].tool_result, {"summary": "Búsqueda completada.", "data": []})
        self.assertEqual(history[2].agent_action_id, action.id)
        self.assertEqual(action.chat_session_id, session.id)
        self.assertEqual(result["message_id"], history[3].id)
        db.close()

    def test_environment_configures_context_message_limit(self):
        db = self.session_factory()
        with patch.dict("os.environ", {"AGENT_MEMORY_MAX_MESSAGES": "7"}):
            memory = PersistentMemory(db)

        self.assertEqual(memory.max_messages, 7)
        db.close()


if __name__ == "__main__":
    unittest.main()
