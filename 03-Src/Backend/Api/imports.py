from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from Backend.Services.importer import import_uploaded_excel

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/imports")
async def import_products(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    db: Session = Depends(get_db),
):
    summary = import_uploaded_excel(file.file, supplier_id, db)
    return {"data": summary, "meta": {"total": summary["read_rows"]}}
