from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_settings


settings = get_settings()
database_url = URL.create(
    "mysql+pymysql",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
    query={"charset": "utf8mb4"},
)
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    # Cada petición obtiene su propia sesión, evitando compartir estado entre solicitudes y garantizando su cierre incluso ante errores.
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()