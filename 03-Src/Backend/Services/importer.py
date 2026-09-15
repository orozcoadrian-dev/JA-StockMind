from __future__ import annotations

import os
import shutil
from datetime import date
from pathlib import Path

from sqlalchemy import select

from Backend.Models.product import Product
from Backend.Models.supplier import Supplier
from Backend.database import SessionLocal
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.normalizer import extract_attributes, normalize_name, parse_price

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True, parents=True)


def _save_uploaded_file(file_like, original_name: str) -> str:
    unique_name = f"{Path(original_name).stem}_{abs(hash(file_like.name))}_{Path(original_name).suffix}"
    target_path = UPLOADS_DIR / unique_name
    if hasattr(file_like, "read"):
        file_like.seek(0)
        with open(target_path, "wb") as destination:
            shutil.copyfileobj(file_like, destination)
    return str(target_path)


def _product_exists(db, supplier_id: int, row_hash: str) -> Product | None:
    return db.execute(
        select(Product).where(Product.supplier_id == supplier_id, Product.row_hash == row_hash)
    ).scalar_one_or_none()


def _row_has_changed(existing: Product, *, provider_code: str, raw_name: str,
                     normalized_name: str, category: str, unit_price: float,
                     unit_of_measure: str, pack_quantity: int) -> bool:
    return (
        existing.provider_code != provider_code
        or existing.raw_name != raw_name
        or existing.normalized_name != normalized_name
        or existing.category != category
        or float(existing.unit_price) != float(unit_price)
        or existing.unit_of_measure != unit_of_measure
        or existing.pack_quantity != pack_quantity
    )


def import_excel_file(file_path: str | Path, supplier_id: int) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"El archivo no existe: {path}")

    reader_data = read_excel_file(path)
    db = SessionLocal()
    summary = {
        "read_rows": reader_data["row_count"],
        "imported_rows": 0,
        "updated_rows": 0,
        "rejected_rows": [],
        "file_path": str(path),
    }

    for row in reader_data["rows"]:
        data = row["data"]
        try:
            provider_code = str(data["provider_code"]).strip()
            raw_name = str(data["raw_name"]).strip()
            unit_price = parse_price(data.get("unit_price"))
            normalized_name = normalize_name(raw_name)
            category = str(data.get("category") or "general").strip().lower() or "general"
            unit_of_measure = str(data.get("unit_of_measure") or "unidad").strip() or "unidad"
            pack_quantity = int(data.get("pack_quantity") or 1)
            row_hash = row["hash"]

            existing = _product_exists(db, supplier_id, row_hash)
            if existing:
                if _row_has_changed(
                    existing,
                    provider_code=provider_code,
                    raw_name=raw_name,
                    normalized_name=normalized_name,
                    category=category,
                    unit_price=unit_price,
                    unit_of_measure=unit_of_measure,
                    pack_quantity=pack_quantity,
                ):
                    existing.provider_code = provider_code
                    existing.raw_name = raw_name
                    existing.normalized_name = normalized_name
                    existing.category = category
                    existing.unit_price = unit_price
                    existing.unit_of_measure = unit_of_measure
                    existing.pack_quantity = pack_quantity
                    existing.price_list_date = date.today()
                    summary["updated_rows"] += 1
                continue

            product = Product(
                supplier_id=supplier_id,
                provider_code=provider_code,
                raw_name=raw_name,
                normalized_name=normalized_name,
                category=category,
                unit_price=unit_price,
                currency="COP",
                unit_of_measure=unit_of_measure,
                pack_quantity=pack_quantity,
                price_list_date=date.today(),
                row_hash=row_hash,
            )
            db.add(product)
            summary["imported_rows"] += 1
            extract_attributes(raw_name)
        except Exception as exc:  # pragma: no cover - safe invalid row handling
            summary["rejected_rows"].append({
                "row_number": row.get("row_number"),
                "reason": str(exc),
            })

    db.commit()
    db.close()
    return summary


def import_uploaded_excel(file, supplier_id: int) -> dict:
    if not file:
        raise ValueError("No se recibió ningún archivo.")

    filename = getattr(file, "filename", "") or "upload.xlsx"
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".xlsx", ".xls", ".csv"}:
        raise ValueError("La extensión del archivo no es válida. Usa .xlsx, .xls o .csv.")

    db = SessionLocal()
    try:
        supplier = db.execute(select(Supplier).where(Supplier.id == supplier_id)).scalar_one_or_none()
        if supplier is None:
            raise ValueError("El proveedor indicado no existe.")

        file_path = _save_uploaded_file(file, filename)
        summary = import_excel_file(file_path, supplier_id)
        summary["stored_file_path"] = file_path
        return summary
    finally:
        db.close()
