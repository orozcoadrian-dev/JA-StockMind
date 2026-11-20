from fastapi import APIRouter
from sqlalchemy import text

from Backend.database import SessionLocal

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    db = SessionLocal()

    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    finally:
        db.close()

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "0.1.0",
    }
