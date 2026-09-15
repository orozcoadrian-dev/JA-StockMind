import unittest
from pathlib import Path

from openpyxl import Workbook

from Backend.database import SessionLocal, init_db
from Backend.Models.product import Product
from Backend.Models.supplier import Supplier
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.importer import import_excel_file
from Backend.Services.normalizer import extract_attributes, normalize_name, parse_price

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_DIR.mkdir(exist_ok=True, parents=True)


def _write_fixture_file(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


class ExcelImportPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        db.query(Product).delete()
        db.query(Supplier).delete()
        existing = db.query(Supplier).filter_by(name="Inversiones Guerrero").first()
        if not existing:
            db.add(Supplier(name="Inversiones Guerrero", nit="900123456-7", contact="Cliente", active=True))
        db.commit()
        db.close()

        guerrer_path = FIXTURE_DIR / "guerrero_grips.xlsx"
        malusa_path = FIXTURE_DIR / "malusa_grips.xlsx"

        _write_fixture_file(
            guerrer_path,
            [
                ["logo", "", ""],
                ["Lista de precios Inversiones Guerrero", "", ""],
                ["Código", "Descripción", "Precio"],
                ["IG-4471", "GRIP ROJO DEPORTIVO", "$ 185.000"],
                ["IG-4472", "GRIP AZUL", "$ 195.000"],
                ["IG-4473", "FILTRO DE ACEITE", "$ 42.000"],
                ["", "", ""],
            ],
        )

        _write_fixture_file(
            malusa_path,
            [
                ["Fecha", "2026-09-01", ""],
                ["SKU", "Nombre", "Valor"],
                ["ML-0892", "Manubrio grip rojo", "190.000"],
                ["ML-0893", "Grip rojo 22mm", "200.000"],
                ["ML-0894", "Grip azul 22mm", "210.000"],
                ["ML-0895", "Freno delantero", "320.000"],
            ],
        )

    def test_excel_reader_detects_header_and_returns_rows(self):
        worksheet_path = FIXTURE_DIR / "guerrero_grips.xlsx"
        result = read_excel_file(worksheet_path)

        self.assertGreater(result["row_count"], 0)
        self.assertIn("header_row", result)
        self.assertIn("rows", result)
        self.assertIn("warnings", result)

    def test_normalizer_handles_colombian_currency_and_names(self):
        self.assertEqual(normalize_name("GRIPS ROJ. UNIV."), "grip rojo universal")
        self.assertEqual(parse_price("$ 12.500"), 12500)
        self.assertEqual(parse_price("12.500,00"), 12500)
        self.assertEqual(extract_attributes("Grip rojo 22mm para moto")["color"], "rojo")

    def test_importer_processes_excel_and_keeps_idempotence(self):
        supplier_id = 1
        file_path = FIXTURE_DIR / "malusa_grips.xlsx"

        first = import_excel_file(file_path, supplier_id)
        second = import_excel_file(file_path, supplier_id)

        self.assertEqual(first["imported_rows"], 4)
        self.assertEqual(second["updated_rows"], 0)
        self.assertEqual(second["imported_rows"], 0)


if __name__ == "__main__":
    unittest.main()
