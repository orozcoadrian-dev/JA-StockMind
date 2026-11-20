import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from Backend.app import app
from app.db.base import Base
from Backend.app.db.session import get_db
from app.models import Category, Import, Product, Supplier


@compiles(mysql.TINYINT, "sqlite")
def compile_mysql_tinyint_for_sqlite(type_, compiler, **kwargs):
    return "INTEGER"


class RestApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(bind=cls.engine, expire_on_commit=False)
        updated_at_default = Product.__table__.c.updated_at.server_default
        Product.__table__.c.updated_at.server_default = text("CURRENT_TIMESTAMP")
        try:
            Base.metadata.create_all(
                cls.engine,
                tables=[
                    Category.__table__,
                    Supplier.__table__,
                    Import.__table__,
                    Product.__table__,
                ],
            )
        finally:
            Product.__table__.c.updated_at.server_default = updated_at_default

        def override_get_db():
            db = cls.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)
        cls.name = f"Proveedor prueba {uuid4().hex[:8]}"
        response = cls.client.post("/api/v1/suppliers", json={"name": cls.name, "nit": f"T-{uuid4().hex[:8]}"})
        cls.supplier = response.json()["data"]

    @classmethod
    def tearDownClass(cls):
        cls.client.delete(f"/api/v1/suppliers/{cls.supplier['id']}")
        app.dependency_overrides.pop(get_db, None)
        cls.engine.dispose()

    def test_create_supplier_returns_location_and_standard_envelope(self):
        response = self.client.get(f"/api/v1/suppliers/{self.supplier['id']}")

        self.assertEqual(response.status_code, 200)
        created = self.client.post("/api/v1/suppliers", json={"name": f"Otro {uuid4().hex[:8]}", "nit": f"T-{uuid4().hex[:8]}"})
        self.assertIn("Location", created.headers)
        self.client.delete(f"/api/v1/suppliers/{created.json()['data']['id']}")
        self.assertIn("data", response.json())
        self.assertIn("meta", response.json())

    def test_list_is_paginated(self):
        response = self.client.get("/api/v1/suppliers?page=1&per_page=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["page"], 1)
        self.assertEqual(response.json()["meta"]["per_page"], 1)

    def test_patch_is_partial(self):
        response = self.client.patch(f"/api/v1/suppliers/{self.supplier['id']}", json={"contact": "contacto parcial"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["contact"], "contacto parcial")

    def test_not_found_and_validation_use_error_envelope(self):
        missing = self.client.get("/api/v1/products/999999999")
        invalid = self.client.post("/api/v1/suppliers", json={"name": ""})

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "HTTP_404")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["error"]["code"], "VALIDATION_ERROR")

    def test_delete_returns_no_content(self):
        response = self.client.post("/api/v1/suppliers", json={"name": f"Borrar {uuid4().hex[:8]}", "nit": f"T-{uuid4().hex[:8]}"})
        supplier_id = response.json()["data"]["id"]

        deleted = self.client.delete(f"/api/v1/suppliers/{supplier_id}")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")


if __name__ == "__main__":
    unittest.main()