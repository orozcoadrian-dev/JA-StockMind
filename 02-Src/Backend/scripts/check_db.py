from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from Backend.database.mysql import MySQLSettings, build_mysql_url


EXPECTED_TABLES = {
    "suppliers",
    "categories",
    "imports",
    "products",
    "canonical_products",
    "product_links",
    "equivalence_rules",
    "agent_actions",
}


def main() -> int:
    try:
        settings = MySQLSettings()
        engine = create_engine(build_mysql_url(settings), pool_pre_ping=True)
    except (OSError, ValueError) as exc:
        print(f"No se pudo leer la configuración de MySQL: {exc}")
        print("Revisa Backend/.env y completa DB_HOST, DB_PORT, DB_NAME y DB_USER.")
        return 1

    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
                print("Conexión a MySQL: correcta (SELECT 1).")
                existing_tables = set(inspect(connection).get_table_names())
        except SQLAlchemyError as exc:
            print("No fue posible conectar o consultar MySQL.")
            print("Inicia MySQL desde XAMPP y verifica DB_HOST, DB_PORT y las credenciales DB_USER/DB_PASSWORD en Backend/.env.")
            print(f"Detalle: {exc.__class__.__name__}")
            return 1

        errors = False
        missing_tables = sorted(EXPECTED_TABLES - existing_tables)
        if missing_tables:
            errors = True
            print(f"Faltan tablas: {', '.join(missing_tables)}.")
            print("Ejecuta en MySQL el script SQL de creación de la base stockmind.")
        else:
            print(f"Tablas verificadas: {len(EXPECTED_TABLES)} de {len(EXPECTED_TABLES)} esperadas.")

        for table_name, expected_count, label, seed_sql in (
            (
                "suppliers",
                4,
                "proveedores",
                "INSERT IGNORE INTO suppliers (name) VALUES "
                "('Inversiones Guerrero'), ('Malusa'), ('Distrimotos'), ('Partes del Caribe');",
            ),
            (
                "categories",
                3,
                "categorías",
                "INSERT IGNORE INTO categories (name) VALUES "
                "('Frenos'), ('Manubrio y controles'), ('Transmisión');",
            ),
        ):
            if table_name not in existing_tables:
                continue

            try:
                with engine.connect() as connection:
                    actual_count = connection.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")
                    ).scalar_one()
            except SQLAlchemyError as exc:
                errors = True
                print(f"No se pudo contar {label} en la tabla {table_name}.")
                print("Revisa que stockmind_user tenga permisos de lectura sobre la base stockmind.")
                print(f"Detalle: {exc.__class__.__name__}")
                continue

            if actual_count != expected_count:
                errors = True
                print(f"Se esperaban {expected_count} {label} y se encontraron {actual_count}.")
                print(f"Completa los datos semilla con: {seed_sql}")
            else:
                print(f"{label.capitalize()}: {actual_count} de {expected_count}.")

        if errors:
            return 1

        print("Verificación de base de datos completada correctamente.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())