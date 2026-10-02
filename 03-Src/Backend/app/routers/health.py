from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..db.session import get_db
from ..schemas.api import APIEnvelope, responses


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=APIEnvelope[dict], responses=responses(503, 500))
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="No fue posible conectar con la base de datos.") from exc

    return {
        "data": {
            "status": "ok",
            "version": get_settings().APP_VERSION,
            "database": "ok",
        },
        "meta": {},
    }