import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from Backend.app import app
from Backend.app.db.session import get_db


class ApiEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(app.dependency_overrides.pop, get_db, None)

    def test_versioned_health_endpoint_is_available(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ok")

    def test_suggest_matches_endpoint_returns_api_envelope(self):
        expected = [{"score": 0.95, "recommendation": "Revisar"}]
        with patch("Backend.Services.api_v1.suggest_matches", return_value=expected):
            response = self.client.post("/api/v1/matches/suggest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], expected)
        self.assertEqual(response.json()["meta"]["total"], 1)

    def test_agent_chat_accepts_eight_thousand_characters_and_rejects_more(self):
        response_body = {
            "session_id": "b86c7b1d-7881-47fc-9cc0-632ccf7564b2",
            "message_id": 1,
            "content": "Respuesta de prueba.",
            "response": "Respuesta de prueba.",
            "tools_used": [],
            "pending_confirmations": [],
        }
        with patch("Backend.Agent.core.agent_core.run", return_value=response_body) as run:
            accepted = self.client.post(
                "/api/v1/agent/chat",
                json={
                    "message": "x" * 8000,
                    "session_id": "b86c7b1d-7881-47fc-9cc0-632ccf7564b2",
                },
            )
            rejected = self.client.post(
                "/api/v1/agent/chat",
                json={"message": "x" * 8001},
            )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(run.call_args.args[0], "x" * 8000)
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.json()["error"]["code"], "VALIDATION_ERROR")

    def test_agent_chat_rejects_non_uuid4_session_ids(self):
        response = self.client.post(
            "/api/v1/agent/chat",
            json={"message": "Consulta", "session_id": "00000000-0000-1000-8000-000000000000"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
