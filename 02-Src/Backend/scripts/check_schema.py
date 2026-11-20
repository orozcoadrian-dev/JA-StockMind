import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.base import Base
import app.models


def _type_signature(column_type, dialect) -> str:
    return " ".join(column_type.compile(dialect=dialect).lower().split())


def compare_schema(engine) -> list[str]:
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)
    issues: list[str] = []

    for table_name in sorted(expected_tables - actual_tables):
        issues.append(f"Falta la tabla '{table_name}'.")
    for table_name in sorted(actual_tables - expected_tables):
        issues.append(f"La tabla '{table_name}' no está definida en los modelos.")

    for table_name in sorted(expected_tables & actual_tables):
        expected_columns = Base.metadata.tables[table_name].columns
        actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}

        for column_name in sorted(set(expected_columns.keys()) - set(actual_columns)):
            issues.append(f"Falta la columna '{table_name}.{column_name}'.")
        for column_name in sorted(set(actual_columns) - set(expected_columns.keys())):
            issues.append(f"La columna '{table_name}.{column_name}' no está definida en el modelo.")

        for column_name in sorted(set(expected_columns.keys()) & set(actual_columns)):
            expected = expected_columns[column_name]
            actual = actual_columns[column_name]
            expected_type = _type_signature(expected.type, engine.dialect)
            actual_type = _type_signature(actual["type"], engine.dialect)
            if expected_type != actual_type:
                issues.append(
                    f"Tipo incorrecto en '{table_name}.{column_name}': "
                    f"modelo={expected_type}, MySQL={actual_type}."
                )
            if expected.nullable != actual["nullable"]:
                expected_nullability = "NULL" if expected.nullable else "NOT NULL"
                actual_nullability = "NULL" if actual["nullable"] else "NOT NULL"
                issues.append(
                    f"Nulabilidad incorrecta en '{table_name}.{column_name}': "
                    f"modelo={expected_nullability}, MySQL={actual_nullability}."
                )

    return issues


def main() -> int:
    engine = None
    try:
        settings = get_settings()
        url = URL.create(
            "mysql+pymysql",
            username=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            query={"charset": "utf8mb4"},
        )
        engine = create_engine(url, pool_pre_ping=True)
        issues = compare_schema(engine)
    except Exception as exc:
        print("No se pudo comparar el esquema con MySQL.")
        print("Verifica que MySQL esté iniciado y que Backend/.env tenga DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD correctos.")
        print(f"Detalle: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    if issues:
        print("El esquema no coincide con los modelos:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Esquema consistente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())