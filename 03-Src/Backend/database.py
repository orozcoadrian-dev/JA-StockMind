import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")

from importlib import import_module

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    import_module("Backend.Models.agent_action")
    import_module("Backend.Models.canonical_product")
    import_module("Backend.Models.equivalence_rule")
    import_module("Backend.Models.import_record")
    import_module("Backend.Models.match_suggestion")
    import_module("Backend.Models.product")
    import_module("Backend.Models.product_link")
    import_module("Backend.Models.supplier")
    Base.metadata.create_all(bind=engine)
