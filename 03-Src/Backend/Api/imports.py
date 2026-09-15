from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from Backend.Services.importer import import_uploaded_excel

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/imports")
async def import_products(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
):
    summary = import_uploaded_excel(file.file, supplier_id)
    return {"data": summary, "meta": {"total": summary["read_rows"]}}
