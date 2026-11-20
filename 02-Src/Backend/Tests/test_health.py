import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_NAME", "stockmind_test")
os.environ.setdefault("DB_USER", "stockmind_test")
os.environ.setdefault("DB_PASSWORD", "")

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.session import get_db
from app.main import app


class HealthEndpointTest(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_returns_standard_success_envelope(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ok")
        self.assertEqual(response.json()["data"]["database"], "ok")
        self.assertIn("meta", response.json())

    def test_database_failure_returns_standard_503_error(self):
        self.db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("offline"))

        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "HTTP_503")
        self.assertEqual(response.json()["error"]["message"], "No fue posible conectar con la base de datos.")

    def test_validation_error_uses_standard_error_envelope(self):
        response = self.client.post("/api/v1/suppliers", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("details", response.json()["error"])

    def test_not_found_uses_spanish_error_envelope(self):
        response = self.client.get("/route-that-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "HTTP_404")
        self.assertEqual(response.json()["error"]["message"], "No se encontró el recurso solicitado.")

    def test_upload_limit_returns_standard_413_error(self):
        response = self.client.post(
            "/api/v1/health",
            content=b"x" * (10 * 1024 * 1024 + 1),
            headers={"content-type": "application/octet-stream"},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "HTTP_413")

    def test_docs_and_redoc_are_enabled(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/redoc").status_code, 200)

    def test_wildcard_cors_origin_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                DB_HOST="localhost",
                DB_PORT=3306,
                DB_NAME="stockmind_test",
                DB_USER="stockmind_test",
                DB_PASSWORD="",
                CORS_ORIGINS="*",
            )