from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.rate_limit import limiter
from ..db.session import get_db
from ..schemas.api import APIEnvelope, ImportDTO, responses
from Backend.Services import api_v1 as service


router = APIRouter(prefix="/imports", tags=["Importaciones"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIEnvelope[ImportDTO], responses=responses(400, 404, 413, 422, 429, 500))
@limiter.limit("30/minute")
async def create_import(request: Request, response: Response, supplier_id: int = Form(..., gt=0), file: UploadFile = File(...), db: Session = Depends(get_db)):
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        from fastapi import HTTPException

        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo permitido.")
    result = service.create_import(db, supplier_id, file.filename or "upload.xlsx", contents)
    response.headers["Location"] = str(request.url_for("get_import", import_id=result["id"]))
    return {"data": result, "meta": {}}


@router.get("", response_model=APIEnvelope[list[ImportDTO]], responses=responses(404, 422, 500))
def list_imports(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), supplier_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db)):
    data, meta = service.list_imports(db, page, per_page, supplier_id)
    return {"data": data, "meta": meta}


@router.get("/{import_id}", name="get_import", response_model=APIEnvelope[ImportDTO], responses=responses(404, 500))
def get_import(import_id: int, db: Session = Depends(get_db)):
    return {"data": service.get_import(db, import_id), "meta": {}}
