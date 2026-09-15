from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import Workbook
from sqlalchemy import select

from Backend.database import SessionLocal, init_db
from Backend.Models.supplier import Supplier
from Backend.Services.importer import import_excel_file
from Backend.Agent.tools import execute_tool

DEMO_DIR = Path(__file__).resolve().parent
PRICE_DATE = date(2026, 9, 1)

SUPPLIERS = [
    ("Inversiones Guerrero", "900123456-7", "Lista Guerrero"),
    ("Malusa", "900654321-9", "Lista Malusa"),
    ("Distrimotos", "901987654-2", "Lista Distrimotos"),
    ("Partes del Caribe", "902456789-5", "Lista Partes del Caribe"),
]

COMMON_PRODUCTS = [
    ("GRIP ROJO DEPORTIVO 22mm", 185000),
    ("GRIP AZUL DEPORTIVO 22mm", 188000),
    ("GRIP ROJO DEPORTIVO 28mm", 195000),
    ("FILTRO DE ACEITE", 42000),
    ("PASTILLA FRENO DELANTERO", 86000),
    ("PASTILLA FRENO TRASERO", 78000),
    ("CABLE ACELERADOR UNIVERSAL", 32000),
    ("CABLE EMBRAGUE UNIVERSAL", 29000),
    ("ESPEJO RETROVISOR DERECHO", 52000),
    ("ESPEJO RETROVISOR IZQUIERDO", 52000),
    ("BUJIA NGK DPR8EA-9", 28000),
    ("CADENA 428H 132 ESLABONES", 118000),
    ("KIT ARRASTRE 428", 245000),
    ("BOMBILLO LED H4", 67000),
    ("RELAY DIRECCIONALES 12V", 18000),
    ("MANIGUETA FRENO NEGRA", 41000),
    ("MANIGUETA EMBRAGUE NEGRA", 41000),
    ("AMORTIGUADOR TRASERO", 310000),
    ("RODAMIENTO RUEDA 6202", 23000),
    ("RETEN HORQUILLA 31MM", 46000),
    ("LLANTA DELANTERA 90/90-18", 226000),
    ("LLANTA TRASERA 100/90-18", 278000),
    ("BATERIA 12V 7AH", 185000),
    ("ACEITE MOTOR 20W50 1L", 36000),
]

EXCLUSIVE_PRODUCTS = [
    ["TAPA LATERAL NEGRA AKT", "SOPORTE GPS UNIVERSAL", "PROTECTOR CARTER ALUMINIO", "CUBIERTA CADENA NEGRA"],
    ["GUANTES URBANOS TALLA M", "MALETERO 28L NEGRO", "SOPORTE CELULAR MANUBRIO", "CUBREPUÑOS TOURING"],
    ["SCANNER OBD MOTO", "KIT LIMPIEZA CADENA", "LINTERNA TALLER USB", "CARGADOR BATERIA 12V"],
    ["PARRILLA TRASERA UNIVERSAL", "BOLSO SOBRE TANQUE 12L", "IMPERMEABLE MOTO TALLA L", "RED ELASTICA EQUIPAJE"],
]

FORMATS = [
    {"filename": "guerrero_demo.xlsx", "supplier": SUPPLIERS[0], "header_row": 2, "headers": ["Código", "Descripción", "Precio"], "code": "IG", "price": lambda value: f"$ {value:,.0f}".replace(",", ".")},
    {"filename": "malusa_demo.xlsx", "supplier": SUPPLIERS[1], "header_row": 4, "headers": ["SKU", "Nombre", "Valor"], "code": "ML", "price": lambda value: f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")},
    {"filename": "distrimotos_demo.xlsx", "supplier": SUPPLIERS[2], "header_row": 1, "headers": ["REFERENCIA", "DETALLE", "COSTO"], "code": "DT", "price": lambda value: str(value)},
    {"filename": "partes_caribe_demo.xlsx", "supplier": SUPPLIERS[3], "header_row": 6, "headers": ["Cod.", "Producto", "Precio unitario"], "code": "PC", "price": lambda value: f"  {value:,.0f}  ".replace(",", ".")},
]


def create_workbook(spec: dict, supplier_index: int) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lista de precios"
    for _ in range(spec["header_row"]):
        sheet.append(["", "", ""])
    sheet.append(spec["headers"])

    rows = list(COMMON_PRODUCTS)
    rows.extend((name, 50000 + (index * 13750)) for index, name in enumerate(EXCLUSIVE_PRODUCTS[supplier_index] * 15))
    for row_index, (name, price) in enumerate(rows, start=1):
        code = f"{spec['code']}-{4470 + row_index:04d}"
        if supplier_index == 0 and row_index == 1:
            name = "GRIP ROJO DEPORTIVO 22mm"
        elif supplier_index == 1 and row_index == 1:
            name = "Manubrio grip rojo 22mm"
        elif supplier_index == 2 and row_index == 1:
            name = "GRIPS ROJ. UNIV. 22mm"
        elif supplier_index == 3 and row_index == 1:
            name = "grip rojo x par 22mm"
        sheet.append([code, name, spec["price"](price + supplier_index * 2500)])
        if row_index == 42:
            sheet.append(["", "", ""])
            sheet.append(["", "SUBTOTAL LISTA", spec["price"](0)])

    output = DEMO_DIR / spec["filename"]
    workbook.save(output)
    return output


def ensure_suppliers() -> dict[str, int]:
    db = SessionLocal()
    try:
        result = {}
        for name, nit, contact in SUPPLIERS:
            supplier = db.scalar(select(Supplier).where(Supplier.name == name))
            if supplier is None:
                supplier = Supplier(name=name, nit=nit, contact=contact, active=True)
                db.add(supplier)
                db.flush()
            result[name] = supplier.id
        db.commit()
        return result
    finally:
        db.close()


def seed_demo() -> None:
    init_db()
    supplier_ids = ensure_suppliers()
    for index, spec in enumerate(FORMATS):
        path = create_workbook(spec, index)
        summary = import_excel_file(path, supplier_ids[spec["supplier"][0]])
        print(f"{path.name}: {summary['read_rows']} filas, {summary['imported_rows']} nuevas, {len(summary['rejected_rows'])} rechazadas")
    result = execute_tool("suggest_matches", {})
    print(result["summary"])


if __name__ == "__main__":
    seed_demo()
    print(f"Archivos demo generados en {DEMO_DIR}")
