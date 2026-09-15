import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "supplier_id": ["supplier_id", "supplier", "proveedor"],
    "provider_code": ["codigo", "cod", "cod.", "codigo proveedor", "referencia", "sku", "id", "part number"],
    "raw_name": ["descripcion", "descripción", "nombre", "producto", "detalle", "item", "nombre producto"],
    "unit_price": ["precio", "valor", "precio unitario", "costo", "precio venta"],
    "unit_of_measure": ["unidad", "uom", "medida", "unidad medida"],
    "pack_quantity": ["cantidad por empaque", "empaque", "cantidad", "cantidad x caja"],
    "availability": ["existencia", "stock", "cantidad disponible"],
    "category": ["categoria", "categoría", "tipo", "linea"],
}


def normalize_column_name(value: str) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip().lower()
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def detect_header_row(frame: pd.DataFrame) -> tuple[int, list[str]]:
    for row_index in range(min(len(frame), 15)):
        candidate = []
        for value in frame.iloc[row_index].tolist():
            if pd.isna(value):
                continue
            cell = unicodedata.normalize("NFKD", str(value).strip().lower())
            cell = "".join(ch for ch in cell if not unicodedata.combining(ch))
            candidate.append(cell)
        if not candidate:
            continue
        matches = sum(
            1
            for cell in candidate
            if any(alias in cell for alias in ["codigo", "cod", "sku", "precio", "valor", "costo", "descripcion", "referencia", "detalle", "producto", "nombre"])
        )
        if matches >= 2:
            return row_index, [str(value) for value in frame.iloc[row_index].tolist()]
    raise ValueError("No se pudo detectar la fila de encabezado real del archivo Excel.")


def map_columns(headers: list[str]) -> dict[str, str]:
    normalized_headers = {normalize_column_name(header): header for header in headers if header is not None}
    mapped = {}

    for canonical_key, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_key = normalize_column_name(alias)
            if alias_key in normalized_headers:
                mapped[canonical_key] = normalized_headers[alias_key]
                break

    missing = [key for key in ["provider_code", "raw_name", "unit_price"] if key not in mapped]
    if missing:
        raise ValueError(f"No se pudieron mapear columnas obligatorias: {', '.join(missing)}")

    return mapped


def row_hash(row: dict) -> str:
    payload = "|".join(str(value or "") for value in row.values())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_excel_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    frame = pd.read_excel(path, header=None, dtype=str)

    if frame.empty:
        raise ValueError("El archivo Excel está vacío.")

    header_row, raw_headers = detect_header_row(frame)
    headers = [str(value).strip() for value in raw_headers]
    mapped_columns = map_columns(headers)

    rows = []
    warnings = []
    for row_index in range(header_row + 1, len(frame)):
        current_row = frame.iloc[row_index].tolist()
        if all(pd.isna(value) or str(value).strip() == "" for value in current_row):
            continue

        data = {}
        for canonical_key, source_header in mapped_columns.items():
            idx = headers.index(source_header)
            if idx < len(current_row):
                value = current_row[idx]
                data[canonical_key] = value

        if not any(str(value).strip() for value in data.values() if value is not None):
            continue

        if "provider_code" in data and str(data["provider_code"]).strip() == "":
            warnings.append(f"Fila {row_index + 1}: código vacío, descartada.")
            continue

        rows.append({"row_number": row_index + 1, "data": data, "hash": row_hash(data)})

    return {
        "header_row": header_row,
        "field_mapping": mapped_columns,
        "row_count": len(rows),
        "rows": rows,
        "warnings": warnings,
    }
