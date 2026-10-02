import os
import unittest
from pathlib import Path

from sqlalchemy import func, select

from app.models import Import, Product, Supplier
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.importer import import_excel_file
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