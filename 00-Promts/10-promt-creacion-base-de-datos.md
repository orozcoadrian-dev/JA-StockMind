Actúa como un arquitecto de datos senior y desarrollador Backend Python experto en Flask y SQLAlchemy 2.0.

Necesito que diseñes y escribas la capa completa de persistencia de datos para el proyecto MotoStock, organizando todo el código relacionado con la base de datos en una carpeta dedicada `backend/database/`.

CONTEXTO DEL SISTEMA:
Es un sistema de consolidación de inventario para repuestos de motos que recibe listas Excel de varios proveedores, normaliza productos, propone equivalencias y ejecuta reglas dictadas en lenguaje natural.

ESTRUCTURA DE ARCHIVOS A CREAR:
backend/database/
├── __init__.py             # Instancia de SQLAlchemy e inicializador de la app
├── seed.py                 # Script para poblar datos semilla
└── models/
    ├── __init__.py
    ├── supplier.py
    ├── product.py
    ├── canonical_product.py
    ├── product_link.py
    ├── equivalence_rule.py
    ├── agent_action.py
    └── schemas.py          # Esquemas Pydantic v2 o Marshmallow

ENTIDADES Y MODELOS A IMPLEMENTAR:
1. Supplier: Proveedores mayoristas (id, name, nit, contact_info, is_active, created_at).
2. Product: Producto crudo (id, supplier_id, supplier_code, raw_name, normalized_name, category, unit_price, currency, unit_of_measure, pack_quantity, price_list_date, raw_row_hash, created_at).
3. CanonicalProduct: Producto unificado (id, canonical_name, category, attributes [JSON], stock_quantity, min_stock, created_at, updated_at).
4. ProductLink: Relación N:1 entre Product y CanonicalProduct (id, product_id, canonical_product_id, confidence_score [Float 0.0 - 1.0], link_source ['rule', 'agent_suggestion', 'manual_confirmation'], confirmed_by, created_at).
5. EquivalenceRule: Reglas del usuario (id, raw_prompt_text, structured_condition [JSON], suppliers_involved [JSON], is_active, rule_type ['equivalence', 'exclusion', 'supplier_preference'], times_applied, created_at).
6. AgentAction: Bitácora del agente (id, timestamp, tool_used, input_params [JSON], execution_result [JSON], requires_confirmation [Boolean], is_approved [Boolean]).

REQUISITOS TÉCNICOS:
1. Usar SQLAlchemy 2.0 con la sintaxis Declarative Mapping (`Mapped` y `mapped_column`).
2. Definir claves foráneas (FK), relaciones bidireccionales (`relationship`), e índices clave en `normalized_name`, `supplier_id`, `supplier_code` y `canonical_product_id`.
3. Crear `database/models/schemas.py` para la serialización y validación estricta de JSON (separando entrada/creación y salida).
4. Diseñar el esquema de validación para `structured_condition` en `EquivalenceRule` (soportando los tipos `supplier_equivalence`, `exclusion` y `preference`).
5. Crear el script `database/seed.py` para insertar los 4 proveedores iniciales (Inversiones Guerrero, Malusa, Distrimotos, Partes del Caribe) y 3 categorías base (Accesorios, Frenos, Motor).
6. Configurar la URL por defecto para que SQLite cree el archivo `.db` automáticamente en `backend/database/motostock.db`.

ENTREGABLE REQUERIDO:
- Código completo de cada archivo dentro de `backend/database/`.
- Todos los modelos ORM y sus esquemas de validación.
- Script `seed.py`.