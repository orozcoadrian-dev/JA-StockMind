import os
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.engine.result import IteratorResult, SimpleResultMetaData

from app.models import Import, Product, Supplier
from Backend.Services.api_v1 import APIServiceError, create_import
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.importer import _bulk_upsert_products, import_excel_file
from Backend.Services.normalizer import extract_attributes, normalize_name, parse_price

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
GUERRERO_FIXTURE = FIXTURE_DIR / "guerrero_grips.xlsx"
RUN_MYSQL_INTEGRATION = (
    os.getenv("RUN_MYSQL_INTEGRATION") == "1"
    and os.getenv("DB_NAME") == "stockmind_test"
)


class ExcelImportPipelineTest(unittest.TestCase):
    def test_excel_reader_detects_header_and_returns_rows(self):
        result = read_excel_file(GUERRERO_FIXTURE)

        self.assertGreater(result["row_count"], 0)
        self.assertIn("header_row", result)
        self.assertIn("rows", result)
        self.assertIn("warnings", result)

    def test_normalizer_handles_colombian_currency_and_names(self):
        self.assertEqual(normalize_name("GRIPS ROJ. UNIV."), "grip rojo universal")
        self.assertEqual(parse_price("$ 12.500"), 12500)
        self.assertEqual(parse_price("12.500,00"), 12500)
        self.assertEqual(extract_attributes("Grip rojo 22mm para moto")["color"], "rojo")

    def test_bulk_insert_uses_core_cursor_rowcount(self):
        db = Mock()
        db.scalars.return_value.all.return_value = []
        db.get_bind.return_value.dialect.name = "mysql"
        db.execute.return_value = IteratorResult(SimpleResultMetaData([]), iter([]))
        db.connection.return_value.execute.return_value.rowcount = 1
        row = {
            "supplier_id": 1,
            "row_hash": "test-hash",
            "supplier_code": "A-1",
            "raw_name": "Grip rojo",
            "normalized_name": "grip rojo",
            "category_id": None,
            "unit_price": 12500,
            "currency": "COP",
            "unit": "unidad",
            "pack_quantity": 1,
            "price_list_date": None,
            "import_id": 1,
        }

        inserted, updated = _bulk_upsert_products(db, [row])

        self.assertEqual((inserted, updated), (1, 0))
        db.connection.return_value.execute.assert_called_once()
        db.execute.assert_not_called()

    def test_import_without_price_column_returns_actionable_validation_error(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Código", "Descripción"])
        worksheet.append(["A-1", "Grip rojo"])
        contents = BytesIO()
        workbook.save(contents)
        contents.seek(0)

        with TemporaryDirectory() as directory:
            stored_path = Path(directory) / "missing-price.xlsx"

            def save_upload(file_like, original_name):
                stored_path.write_bytes(file_like.read())
                return str(stored_path)

            with patch("Backend.Services.api_v1._save_uploaded_file", side_effect=save_upload):
                with self.assertRaises(APIServiceError) as raised:
                    create_import(Mock(get=Mock(return_value=object())), 1, stored_path.name, contents.getvalue())

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("columnas requeridas", raised.exception.message)
        self.assertIn("unit_price", raised.exception.details["reason"])
        self.assertIn("Precio, valor o costo", raised.exception.details["required_columns"])
        self.assertFalse(stored_path.exists())

    @unittest.skipUnless(
        RUN_MYSQL_INTEGRATION,
        "Activa RUN_MYSQL_INTEGRATION=1 y DB_NAME=stockmind_test para probar MySQL.",
    )
    def test_mysql_import_is_idempotent_and_records_each_load(self):
        from app.db.session import SessionLocal

        result = read_excel_file(GUERRERO_FIXTURE)
        hashes = [row["hash"] for row in result["rows"]]
        db = SessionLocal()
        try:
            supplier = next(
                (item for item in db.scalars(select(Supplier)).all()
                 if item.name == "Inversiones Guerrero"),
                None,
            )
            self.assertIsNotNone(supplier, "Falta el proveedor Inversiones Guerrero en stockmind_test.")
            before_products = db.scalar(
                select(func.count()).select_from(Product).where(
                    Product.supplier_id == supplier.id,
                    Product.row_hash.in_(hashes),
                )
            )
            before_imports = db.scalar(
                select(func.count()).select_from(Import).where(
                    Import.supplier_id == supplier.id,
                    Import.original_filename == GUERRERO_FIXTURE.name,
                )
            )

            first = import_excel_file(GUERRERO_FIXTURE, supplier.id, db)
            second = import_excel_file(GUERRERO_FIXTURE, supplier.id, db)

            after_products = db.scalar(
                select(func.count()).select_from(Product).where(
                    Product.supplier_id == supplier.id,
                    Product.row_hash.in_(hashes),
                )
            )
            after_imports = db.scalar(
                select(func.count()).select_from(Import).where(
                    Import.supplier_id == supplier.id,
                    Import.original_filename == GUERRERO_FIXTURE.name,
                )
            )
            self.assertGreater(first["imported_rows"], 0)
            self.assertEqual(second["imported_rows"], 0)
            self.assertEqual(after_products, before_products + first["imported_rows"])
            self.assertEqual(after_imports, before_imports + 2)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()