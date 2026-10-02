from __future__ import annotations

import os
import re
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import Category, Import, ImportStatus, Product, Supplier
from Backend.Services.excel_reader import read_excel_file
from Backend.Services.normalizer import extract_attributes, normalize_name, parse_price

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True, parents=True)
IMPORT_BATCH_SIZE = 500


def _save_uploaded_file(file_like, original_name: str) -> str:
    unique_name = f"{Path(original_name).stem}_{uuid4().hex}{Path(original_name).suffix}"
    target_path = UPLOADS_DIR / unique_name
    file_like.seek(0)
    with open(target_path, "wb") as destination:
        shutil.copyfileobj(file_like, destination)
    return str(target_path)


def _category_ids(db: Session) -> dict[str, int]:
    # Compare normalized names in Python; MySQL's default collation is accent-insensitive.
    return {normalize_name(category.name): category.id for category in db.scalars(select(Category)).all()}


def _bulk_upsert_products(db: Session, rows: list[dict]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    supplier_id = rows[0]["supplier_id"]
    existing_products = db.scalars(select(Product).where(
        Product.supplier_id == supplier_id,
        Product.row_hash.in_([row["row_hash"] for row in rows]),
    )).all()
    existing_by_hash = {product.row_hash: product for product in existing_products}
    updates = []
    update_fields = (
        "supplier_code",
        "raw_name",
        "normalized_name",
        "category_id",
        "unit_price",
        "currency",
        "unit",
        "pack_quantity",
        "price_list_date",
    )
    for row in rows:
        existing = existing_by_hash.get(row["row_hash"])
        if existing is None:
            continue
        changed_values = {field: row[field] for field in update_fields if getattr(existing, field) != row[field]}
        if changed_values:
            changed_values["id"] = existing.id
            updates.append(changed_values)

    new_rows = [row for row in rows if row["row_hash"] not in existing_by_hash]
    dialect = db.get_bind().dialect.name
    if dialect == "mysql":
        statement = mysql_insert(Product).prefix_with("IGNORE")
    elif dialect == "sqlite":
        statement = sqlite_insert(Product).on_conflict_do_nothing(
            index_elements=["supplier_id", "row_hash"]
        )
    else:
        statement = insert(Product)
    result = db.execute(statement, new_rows) if new_rows else None
    if updates:
        db.execute(update(Product), updates, execution_options={"synchronize_session": False})
    inserted_count = max(result.rowcount or 0, 0) if result is not None else 0
    return inserted_count, len(updates)


def import_excel_file(
    file_path: str | Path,
    supplier_id: int,
    db: Session,
    *,
    original_filename: str | None = None,
    stored_path: str | None = None,
) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"El archivo no existe: {path}")

    reader_data = read_excel_file(path)
    summary = {
        "read_rows": reader_data["row_count"] + len(reader_data["warnings"]),
        "imported_rows": 0,
        "updated_rows": 0,
        "rejected_rows": [],
        "file_path": str(path),
    }
    for warning in reader_data["warnings"]:
        match = re.match(r"Fila (\d+):\s*(.*)", warning)
        summary["rejected_rows"].append({
            "row_number": int(match.group(1)) if match else None,
            "reason": match.group(2) if match else warning,
        })
    products_to_insert = []
    category_ids = _category_ids(db)

    for row in reader_data["rows"]:
        data = row["data"]
        try:
            supplier_code = str(data.get("provider_code") or "").strip()
            raw_name = str(data.get("raw_name") or "").strip()
            unit_price = Decimal(str(parse_price(data.get("unit_price")))).quantize(Decimal("0.01"))
            normalized_name = normalize_name(raw_name)
            category_name = normalize_name(str(data.get("category") or ""))
            unit = str(data.get("unit_of_measure") or "unidad").strip() or "unidad"
            pack_quantity = int(data.get("pack_quantity") or 1)
            if not raw_name or len(raw_name) > 255 or len(normalized_name) > 255:
                raise ValueError("El nombre del producto está vacío o supera 255 caracteres.")
            if len(supplier_code) > 60 or len(unit) > 20:
                raise ValueError("El código supera 60 caracteres o la unidad supera 20.")
            if unit_price < 0 or unit_price > Decimal("9999999999.99"):
                raise ValueError("El precio está fuera del rango permitido.")
            if pack_quantity < 1:
                raise ValueError("La cantidad por empaque debe ser mayor que cero.")
            extract_attributes(raw_name)
            products_to_insert.append({
                "supplier_id": supplier_id,
                "supplier_code": supplier_code or None,
                "raw_name": raw_name,
                "normalized_name": normalized_name,
                "category_id": category_ids.get(category_name),
                "unit_price": unit_price,
                "currency": "COP",
                "unit": unit,
                "pack_quantity": pack_quantity,
                "price_list_date": date.today(),
                "row_hash": row["hash"],
            })
        except (TypeError, ValueError, ArithmeticError) as exc:
            summary["rejected_rows"].append({"row_number": row.get("row_number"), "reason": str(exc)})

    import_record = Import(
        supplier_id=supplier_id,
        original_filename=original_filename or path.name,
        stored_path=stored_path or str(path),
        status=ImportStatus.PROCESSING,
        rows_read=summary["read_rows"],
    )
    try:
        transaction = db.begin_nested() if db.in_transaction() else db.begin()
        with transaction:
            db.add(import_record)
            db.flush()
            for offset in range(0, len(products_to_insert), IMPORT_BATCH_SIZE):
                batch = products_to_insert[offset:offset + IMPORT_BATCH_SIZE]
                for product_data in batch:
                    product_data["import_id"] = import_record.id
                imported, updated = _bulk_upsert_products(db, batch)
                summary["imported_rows"] += imported
                summary["updated_rows"] += updated
            import_record.rows_imported = summary["imported_rows"]
            import_record.rows_updated = summary["updated_rows"]
            import_record.rows_rejected = len(summary["rejected_rows"])
            import_record.rejection_report = summary["rejected_rows"] or None
            import_record.status = ImportStatus.COMPLETED
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_import = Import(
            supplier_id=supplier_id,
            original_filename=original_filename or path.name,
            stored_path=stored_path or str(path),
            status=ImportStatus.FAILED,
            rows_read=summary["read_rows"],
            rows_rejected=len(summary["rejected_rows"]),
            rejection_report=summary["rejected_rows"] or [{"row_number": None, "reason": str(exc)}],
        )
        try:
            db.add(failed_import)
            db.commit()
        except Exception:
            db.rollback()
        raise
    summary["import_id"] = import_record.id
    return summary


def import_uploaded_excel(file, supplier_id: int, db: Session) -> dict:
    if not file:
        raise ValueError("No se recibió ningún archivo.")

    filename = getattr(file, "filename", "") or "upload.xlsx"
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".xlsx", ".xls", ".csv"}:
        raise ValueError("La extensión del archivo no es válida. Usa .xlsx, .xls o .csv.")

    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise ValueError("El proveedor indicado no existe.")
    file_path = _save_uploaded_file(file, filename)
    summary = import_excel_file(
        file_path,
        supplier_id,
        db,
        original_filename=filename,
        stored_path=file_path,
    )
    summary["stored_file_path"] = file_path
    return summary
