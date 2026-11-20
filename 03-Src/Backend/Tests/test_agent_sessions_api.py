import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.errors import register_exception_handlers
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
from app.models import AgentAction, ChatMessage, ChatSession
from app.routers.agent_sessions import router


@compiles(mysql.TINYINT, "sqlite")
def compile_mysql_tinyint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


@compiles(mysql.LONGTEXT, "sqlite")
def compile_mysql_longtext_for_sqlite(type_, compiler, **kwargs):
    return "TEXT"


class AgentSessionsApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        updated_at_default = ChatSession.__table__.c.updated_at.server_default
        ChatSession.__table__.c.updated_at.server_default = text("CURRENT_TIMESTAMP")
        try:
            Base.metadata.create_all(
                self.engine,
                tables=[
                    ChatSession.__table__,
                    AgentAction.__table__,
                    ChatMessage.__table__,
                ],
            )
        finally:
            ChatSession.__table__.c.updated_at.server_default = updated_at_default
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.app = FastAPI()
        self.app.state.limiter = limiter
        self.app.include_router(router, prefix="/api/v1")
        register_exception_handlers(self.app)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)
        self.addCleanup(self.engine.dispose)

    def _create_session(self, title="Conversación de prueba"):
        response = self.client.post("/api/v1/agent/sessions", json={"title": title})
        self.assertEqual(response.status_code, 201)
        return response.json()["data"]

    def test_create_list_detail_and_patch_session(self):
        created = self._create_session()
        session_id = created["external_id"]

        listed = self.client.get("/api/v1/agent/sessions?status=all&limit=5&offset=0")
        detail = self.client.get(f"/api/v1/agent/sessions/{session_id}")
        renamed = self.client.patch(
            f"/api/v1/agent/sessions/{session_id}",
            json={"title": "Título nuevo"},
        )
        archived = self.client.patch(
            f"/api/v1/agent/sessions/{session_id}",
            json={"status": "archived"},
        )
        reactivated = self.client.patch(
            f"/api/v1/agent/sessions/{session_id}",
            json={"status": "active"},
        )

        self.assertEqual(listed.json()["meta"], {"total": 1, "limit": 5, "offset": 0})
        self.assertEqual(detail.json()["data"]["external_id"], session_id)
        self.assertEqual(renamed.json()["data"]["title"], "Título nuevo")
        self.assertEqual(archived.json()["data"]["status"], "archived")
        self.assertEqual(reactivated.json()["data"]["status"], "active")

    def test_message_listing_defaults_to_user_and_assistant_and_export_keeps_tools(self):
        session = self._create_session()
        db = self.session_factory()
        try:
            session_row = db.query(ChatSession).filter_by(external_id=session["external_id"]).one()
            db.add_all(
                [
                    ChatMessage(session_id=session_row.id, seq=1, role="user", content="Pregunta"),
                    ChatMessage(
                        session_id=session_row.id,
                        seq=2,
                        role="assistant",
                        content="Llamando herramienta",
                        tool_calls=[{"id": "call-1", "function": {"name": "search_products"}}],
                    ),
                    ChatMessage(
                        session_id=session_row.id,
                        seq=3,
                        role="tool",
                        content='{"data": []}',
                        tool_name="search_products",
                        tool_call_id="call-1",
                        tool_result={"data": []},
                    ),
                    ChatMessage(session_id=session_row.id, seq=4, role="assistant", content="Sin resultados."),
                ]
            )
            db.commit()
        finally:
            db.close()

        default_messages = self.client.get(
            f"/api/v1/agent/sessions/{session['external_id']}/messages"
        ).json()["data"]
        all_messages = self.client.get(
            f"/api/v1/agent/sessions/{session['external_id']}/messages?include_tools=true&before_seq=4"
        ).json()["data"]
        exported = self.client.get(
            f"/api/v1/agent/sessions/{session['external_id']}/export"
        ).json()["data"]["messages"]

        self.assertEqual([item["role"] for item in default_messages], ["user", "assistant", "assistant"])
        self.assertEqual([item["seq"] for item in all_messages], [1, 2, 3])
        self.assertEqual(exported[1]["tool_calls"][0]["id"], "call-1")
        self.assertEqual(exported[2]["tool_result"], {"data": []})

    def test_invalid_or_missing_session_returns_standard_errors(self):
        invalid_uuid = self.client.get("/api/v1/agent/sessions/not-a-uuid")
        missing_session = self.client.get(f"/api/v1/agent/sessions/{uuid4()}")
        empty_patch = self.client.patch(f"/api/v1/agent/sessions/{uuid4()}", json={})

        self.assertEqual(invalid_uuid.status_code, 422)
        self.assertEqual(missing_session.status_code, 404)
        self.assertEqual(missing_session.json()["error"]["code"], "CHAT_SESSION_NOT_FOUND")
        self.assertEqual(empty_patch.status_code, 422)
        self.assertEqual(
            self.client.get("/api/v1/agent/sessions").status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/agent/sessions/{uuid4()}").status_code,
            405,
        )


if __name__ == "__main__":
    unittest.main()
