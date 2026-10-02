# JA-Stockmind (MotoStock) — Migración a FastAPI + MySQL

Continuación del archivo `09-promt-reestructuracion-JA-Stockmind.md`. Aquí se
reemplaza el backend Flask por FastAPI y SQLite por MySQL, sin cambiar el dominio
ni los contratos que el frontend ya consume.

Stack nuevo:

| Antes | Ahora |
|-------|-------|
| Flask + blueprints | FastAPI + routers |
| SQLite | MySQL (XAMPP o MySQL 8) |
| Marshmallow / Pydantic suelto | Pydantic v2 (nativo de FastAPI) |
| `openapi.yaml` escrito a mano | Swagger automático en `/docs` |
| Flask-CORS | `CORSMiddleware` |

---

## Orden de ejecución

Un prompt por conversación o sesión. Cada uno asume que el anterior ya quedó
funcionando.

| # | Prompt | Qué deja listo | Cómo verificas antes de seguir |
|---|--------|----------------|-------------------------------|
| 0 | Diagnóstico del error fetch | Causa identificada | Sabes si es servidor caído, URL o CORS |
| 1 | Actualizar `agent.md` | Contexto con el stack nuevo | `agent.md` menciona FastAPI y MySQL |
| 2 | Base de datos MySQL | Tablas creadas con datos semilla | `SHOW TABLES;` lista 8 tablas |
| 3 | Esqueleto FastAPI + conexión | Servidor que levanta y toca MySQL | `/api/v1/health` dice `database: ok` |
| 4 | Modelos y esquemas | SQLAlchemy + Pydantic sobre las tablas | Script de verificación de esquema pasa |
| 5 | Migrar servicios | Ingesta, matcher y reglas sobre MySQL | Importas un `.xlsx` y las filas quedan en MySQL |
| 6 | Migrar la API | Todos los endpoints en routers | Todo responde desde `/docs` |
| 7 | Migrar el agente | Tools y loop contra FastAPI/MySQL | Le dictas una regla y queda en `equivalence_rules` |
| 8 | Conectar el frontend | `api.js` apuntando a FastAPI | El flujo completo funciona sin "Failed to fetch" |
| 9 | Pruebas y verificación | Tests + README actualizado | Proyecto levanta desde cero siguiendo el README |

**Por qué la base de datos va antes del esqueleto.** FastAPI necesita una base real
a la cual conectarse para que `/health` tenga sentido. Y si las tablas las defines tú
con SQL, los modelos de Python (prompt 4) se escriben para calzar con ellas, no al
revés. Así sabes exactamente qué hay en MySQL.

---

## Prompt 0 — Diagnóstico del "Failed to fetch"

> Antes de migrar, entiende qué falló. Si la causa es CORS o una URL mal puesta,
> seguiría pasando con FastAPI.

**Qué significa el error.** `Failed to fetch` aparece cuando el navegador nunca
recibió respuesta: el servidor estaba apagado, el puerto o la URL estaban mal, o el
navegador bloqueó la petición por CORS. Si el servidor hubiera respondido con un 404
o un 500, verías ese código, no `Failed to fetch`.

**Revisa tú primero (2 minutos).** Abre DevTools (F12):

1. Pestaña **Console**: copia el mensaje completo. Si menciona `CORS policy` o
   `Access-Control-Allow-Origin`, es CORS.
2. Pestaña **Network**: mira la petición fallida. Si sale en rojo sin código de
   estado, nunca llegó al servidor.
3. Confirma que el backend estaba corriendo y en qué puerto.
4. Mira cómo abres el frontend. Si lo abres con doble clic (`file:///...`), el origen
   es `null` y CORS lo bloquea casi siempre.

**Si quieres que el asistente lo diagnostique**, pégale esto junto con el mensaje
de la consola:

```
Lee agent.md.

Mi frontend lanza "TypeError: Failed to fetch" al llamar al backend. Necesito la
causa, no una lista de posibilidades.

Revisa en este orden y dime cuál aplica:
1. La URL base que usa frontend/assets/js/api.js (protocolo, host, puerto, prefijo
   /api o /api/v1) contra la ruta y puerto reales del backend.
2. La configuración de CORS del backend contra el origen real desde donde abro el
   frontend (por ejemplo http://127.0.0.1:5500 y http://localhost:5500 son orígenes
   distintos).
3. Si el endpoint que falla responde bien con curl. Si curl funciona y el navegador
   no, es CORS u origen.
4. Si la respuesta de error del backend es JSON o HTML.

Mensaje exacto de la consola:
<PEGA AQUÍ EL MENSAJE>

Entrégame: la causa confirmada, el cambio exacto para arreglarla y el comando curl
con el que lo verifiqué. No cambies nada más.
```

---

## Prompt 1 — Actualizar el contexto maestro

```
Lee agent.md.

Vamos a migrar el backend de Flask a FastAPI y la base de datos de SQLite a MySQL.
No toques código todavía. Solo actualiza agent.md:

1. En STACK, reemplaza:
   - Backend: Python 3.11 + FastAPI + Uvicorn
   - Datos: MySQL (utf8mb4, InnoDB) vía SQLAlchemy 2.x con el driver PyMySQL
   - Validación: Pydantic v2
   - Configuración: pydantic-settings leyendo .env
2. En "Decisiones tomadas" agrega, con el porqué de cada una:
   - FastAPI en vez de Flask: validación y documentación automáticas, tipado.
   - MySQL en vez de SQLite: acceso concurrente y datos reales del almacén.
   - SQLAlchemy síncrono con PyMySQL: pandas y openpyxl son síncronos; un driver
     asíncrono añadiría complejidad sin beneficio aquí.
   - El script SQL es la fuente de verdad del esquema; los modelos se escriben para
     calzar con él y no se usa create_all().
   - Se conservan los contratos: éxito {"data","meta"}, error {"error":{...}}, y el
     prefijo /api/v1, para que el frontend no cambie de contrato.
3. En "Estado del proyecto" anota: "Migración Flask→FastAPI + MySQL en curso;
   lógica de servicios sin cambios".

Cuando termines, muéstrame solo las secciones modificadas.
```

---

## Prompt 2 — Base de datos MySQL

Este prompt tiene dos partes: **A)** el SQL que pegas tú en MySQL, y **B)** el
prompt para el asistente.

### Parte A — SQL para pegar en MySQL

**Dónde pegarlo.**
- **phpMyAdmin (XAMPP):** inicia Apache y MySQL desde el panel de XAMPP, abre
  `http://localhost/phpmyadmin`, pestaña **SQL**, pega todo y pulsa **Continuar**.
- **MySQL Workbench:** abre una pestaña de consulta, pega todo y ejecuta con el rayo.

Antes de ejecutar, cambia `CAMBIA_ESTA_CLAVE` por una clave tuya. Esa misma clave
va después en el `.env`. El script se puede correr más de una vez sin duplicar datos.

```sql
-- =====================================================================
-- JA-Stockmind / MotoStock — Base de datos
-- Compatible con MySQL 8 y MariaDB (XAMPP)
-- =====================================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS stockmind
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stockmind;

-- ---------------------------------------------------------------------
-- 1. Usuario de la aplicación (no uses root desde el backend)
-- ---------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'stockmind_user'@'localhost' IDENTIFIED BY 'CAMBIA_ESTA_CLAVE';
GRANT ALL PRIVILEGES ON stockmind.* TO 'stockmind_user'@'localhost';
FLUSH PRIVILEGES;

-- ---------------------------------------------------------------------
-- 2. Proveedores
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(120) NOT NULL,
  nit         VARCHAR(30)  NULL,
  contact     VARCHAR(150) NULL,
  active      TINYINT(1)   NOT NULL DEFAULT 1,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_suppliers_name (name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. Categorías
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
  id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name  VARCHAR(80)  NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. Importaciones (un registro por Excel subido)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS imports (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  supplier_id       INT UNSIGNED NOT NULL,
  original_filename VARCHAR(255) NOT NULL,
  stored_path       VARCHAR(500) NOT NULL,
  status            ENUM('processing','completed','failed') NOT NULL DEFAULT 'processing',
  rows_read         INT UNSIGNED NOT NULL DEFAULT 0,
  rows_imported     INT UNSIGNED NOT NULL DEFAULT 0,
  rows_updated      INT UNSIGNED NOT NULL DEFAULT 0,
  rows_rejected     INT UNSIGNED NOT NULL DEFAULT 0,
  rejection_report  JSON NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_imports_supplier (supplier_id),
  CONSTRAINT fk_imports_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. Productos tal como los manda el proveedor
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  supplier_id      INT UNSIGNED NOT NULL,
  import_id        INT UNSIGNED NULL,
  category_id      INT UNSIGNED NULL,
  supplier_code    VARCHAR(60)  NULL,
  raw_name         VARCHAR(255) NOT NULL,
  normalized_name  VARCHAR(255) NOT NULL,
  unit_price       DECIMAL(12,2) NOT NULL,
  currency         CHAR(3)      NOT NULL DEFAULT 'COP',
  unit             VARCHAR(20)  NULL,
  pack_quantity    INT UNSIGNED NOT NULL DEFAULT 1,
  price_list_date  DATE NULL,
  row_hash         CHAR(64)     NOT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_products_supplier_hash (supplier_id, row_hash),
  KEY idx_products_normalized_name (normalized_name),
  KEY idx_products_supplier_code (supplier_id, supplier_code),
  KEY idx_products_category (category_id),
  KEY idx_products_import (import_id),
  CONSTRAINT fk_products_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
  CONSTRAINT fk_products_import
    FOREIGN KEY (import_id) REFERENCES imports (id) ON DELETE SET NULL,
  CONSTRAINT fk_products_category
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. Productos canónicos (el producto real, unificado)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canonical_products (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  canonical_name  VARCHAR(255) NOT NULL,
  category_id     INT UNSIGNED NULL,
  attributes      JSON NULL,
  stock           INT NOT NULL DEFAULT 0,
  min_stock       INT NOT NULL DEFAULT 0,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_canonical_name (canonical_name),
  KEY idx_canonical_category (category_id),
  CONSTRAINT fk_canonical_category
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. Vínculos producto <-> producto canónico (también las coincidencias
--    pendientes de revisión: status = 'pending')
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_links (
  id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id            INT UNSIGNED NOT NULL,
  canonical_product_id  INT UNSIGNED NOT NULL,
  confidence            DECIMAL(4,3) NOT NULL,
  origin                ENUM('rule','agent_suggestion','manual') NOT NULL,
  status                ENUM('pending','confirmed','rejected') NOT NULL DEFAULT 'pending',
  reasons               JSON NULL,
  confirmed_by          VARCHAR(80) NULL,
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_link_product_canonical (product_id, canonical_product_id),
  KEY idx_links_canonical (canonical_product_id),
  KEY idx_links_status (status),
  CONSTRAINT fk_links_product
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
  CONSTRAINT fk_links_canonical
    FOREIGN KEY (canonical_product_id) REFERENCES canonical_products (id) ON DELETE CASCADE,
  CONSTRAINT chk_links_confidence CHECK (confidence >= 0 AND confidence <= 1)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. Reglas que dicta el usuario
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equivalence_rules (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  original_text   TEXT NOT NULL,
  rule_type       ENUM('equivalence','exclusion','purchase_preference') NOT NULL,
  condition_json  JSON NOT NULL,
  suppliers       JSON NULL,
  active          TINYINT(1) NOT NULL DEFAULT 1,
  times_applied   INT UNSIGNED NOT NULL DEFAULT 0,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_rules_type_active (rule_type, active)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. Bitácora del agente
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_actions (
  id                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id             VARCHAR(64) NULL,
  tool                   VARCHAR(60) NOT NULL,
  input_params           JSON NULL,
  result                 JSON NULL,
  required_confirmation  TINYINT(1) NOT NULL DEFAULT 0,
  approved               TINYINT(1) NULL,
  created_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_actions_session (session_id),
  KEY idx_actions_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 10. Datos semilla
-- ---------------------------------------------------------------------
INSERT IGNORE INTO suppliers (name) VALUES
  ('Inversiones Guerrero'),
  ('Malusa'),
  ('Distrimotos'),
  ('Partes del Caribe');

INSERT IGNORE INTO categories (name) VALUES
  ('Frenos'),
  ('Manubrio y controles'),
  ('Transmisión');
```

**Verifica que quedó bien.** Ejecuta esto y confirma que ves 8 tablas, 4 proveedores
y 3 categorías (la lista de tablas debe incluir `suppliers`, `categories`, `imports`,
`products`, `canonical_products`, `product_links`, `equivalence_rules`,
`agent_actions`):

```sql
USE stockmind;
SHOW TABLES;
SELECT * FROM suppliers;
SELECT * FROM categories;
```

**Notas.**
- Los tres nombres de categoría son un punto de partida. Cámbialos o agrega más con
  `INSERT` antes de importar datos reales.
- Las columnas `JSON` funcionan en MySQL 8 y en MariaDB (donde son alias de texto con
  validación). SQLAlchemy las maneja igual en ambos.
- `uq_products_supplier_hash` es lo que hace idempotente la reimportación: la misma
  fila del mismo proveedor no se duplica.

### Parte B — Prompt para el asistente

```
Lee agent.md.

La base de datos MySQL "stockmind" ya está creada con el script SQL (8 tablas,
usuario stockmind_user, datos semilla). No la recrees ni la modifiques.

Tu tarea es solo dejar la conexión lista y verificada:

1. Instala las dependencias: sqlalchemy>=2.0, pymysql, cryptography,
   pydantic-settings. Fija versiones en requirements.txt.
2. Crea backend/.env.example con estas variables, sin valores reales:
     DB_HOST=localhost
     DB_PORT=3306
     DB_NAME=stockmind
     DB_USER=stockmind_user
     DB_PASSWORD=
     CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
     LLM_API_KEY=
     MAX_UPLOAD_MB=10
   y confirma que .env está en .gitignore.
3. Construye la URL de conexión con sqlalchemy.engine.URL.create(), no concatenando
   strings, para que una clave con caracteres especiales no rompa la conexión.
   Driver: mysql+pymysql, con charset utf8mb4.
4. Crea un script backend/scripts/check_db.py que se conecte y verifique:
   - que la conexión responde (SELECT 1),
   - que existen las 8 tablas esperadas,
   - que suppliers tiene 4 filas y categories tiene 3.
   Cada fallo debe imprimir un mensaje en español que diga qué falta y cómo
   arreglarlo (por ejemplo: "MySQL no está corriendo, inícialo desde XAMPP").

No uses create_all(). No crees tablas desde Python.

Entrégame: el comando para correr check_db.py y su salida esperada.
```

---

## Prompt 3 — Esqueleto FastAPI + conexión

```
Lee agent.md. La base MySQL ya está creada y check_db.py pasa.

Reemplaza el esqueleto Flask por uno de FastAPI. Estructura exacta:

backend/
├── app/
│   ├── main.py             # crea la app, registra routers y handlers, nada más
│   ├── core/
│   │   ├── config.py       # Settings con pydantic-settings, lee .env
│   │   ├── errors.py       # excepciones propias y handlers globales
│   │   └── logging.py      # logging a consola y archivo
│   ├── db/
│   │   ├── session.py      # engine, SessionLocal y dependencia get_db
│   │   └── base.py         # DeclarativeBase
│   ├── models/             # SQLAlchemy (prompt 4)
│   ├── schemas/            # Pydantic (prompt 4)
│   ├── routers/
│   │   └── health.py
│   ├── services/
│   └── agent/
├── uploads/                # ignorado por git
├── scripts/check_db.py
├── tests/test_health.py
├── requirements.txt
└── .env.example

REQUISITOS
- Todos los routers cuelgan de /api/v1. Health queda en GET /api/v1/health y
  devuelve {"data": {"status": "ok", "version": "...", "database": "ok"|"error"}}.
  Si la base no responde, devuelve 503 con el formato de error, no un 500 mudo.
- Sesión de base por petición con la dependencia get_db (yield, y cierra siempre
  en finally), inyectada con Depends. Explícame en un comentario por qué se hace así.
- CORSMiddleware con allow_origins leído de CORS_ORIGINS (lista separada por comas).
  Nada de "*" si allow_credentials está activo.
- Conserva el contrato de errores del proyecto:
  {"error": {"code": "...", "message": "...", "details": {...}}}
  FastAPI por defecto responde 422 con otra forma ({"detail": [...]}) y las
  HTTPException con {"detail": "..."}. Sobrescribe los handlers de
  RequestValidationError, HTTPException y Exception para que TODAS las respuestas de
  error sigan nuestro formato, con mensajes en español. Cubre 400, 404, 409, 413,
  422, 429, 500 y 503.
- Éxito siempre {"data": ..., "meta": ...}.
- Límite de tamaño de subida según MAX_UPLOAD_MB.
- La documentación automática queda en /docs y /redoc.
- Falla ruidosamente al arrancar si faltan variables obligatorias de la base.

ENTREGABLE
La estructura creada y los comandos exactos para crear el entorno virtual, instalar
y levantar con:
    uvicorn app.main:app --reload --port 8000
en Windows y en Linux. Y el comando curl para probar /api/v1/health, con la salida
esperada.

Elimina el código Flask (app.py, blueprints, Flask-CORS) cuando el health de
FastAPI esté verificado, no antes. Actualiza "Estado del proyecto" en agent.md.
```

---

## Prompt 4 — Modelos SQLAlchemy y esquemas Pydantic

```
Lee agent.md. FastAPI levanta y /health confirma la conexión con MySQL.

Escribe los modelos de Python para que calcen EXACTAMENTE con las tablas que ya
existen en MySQL. El script SQL es la fuente de verdad: no inventes columnas ni
cambies tipos.

TAREA
1. backend/app/models/: un archivo por entidad con SQLAlchemy 2.x (Mapped y
   mapped_column): Supplier, Category, Import, Product, CanonicalProduct,
   ProductLink, EquivalenceRule, AgentAction.
   - Dinero con Decimal / Numeric(12, 2), nunca float.
   - Columnas JSON con sqlalchemy.JSON.
   - Enums de Python para origin, status, rule_type e import status.
   - relationship() solo donde se use de verdad.
2. backend/app/schemas/: Pydantic v2, separando entrada (Create/Update) y salida
   (Read, con from_attributes=True). Incluye el esquema de listados paginados con
   meta (total, page, per_page, pages).
   - Valida el formato de la condición estructurada de EquivalenceRule según los
     tres tipos: equivalencia, exclusión y preferencia de compra.
3. backend/scripts/check_schema.py: compara los modelos contra la base real con
   sqlalchemy.inspect() y reporta tablas o columnas que no calzan, en español.
4. Pruebas: un JSON correcto pasa y varios incorrectos fallan con mensaje claro
   (precio negativo, confianza fuera de 0 a 1, tipo de regla desconocido).

No uses Base.metadata.create_all().
Pruebas de integración contra una base de prueba separada (stockmind_test), no
contra la de desarrollo. Dime qué comandos SQL debo correr para crearla.

Verificación: check_schema.py debe terminar con "Esquema consistente".
```

---

## Prompt 5 — Migrar los servicios a MySQL

```
Lee agent.md. Los modelos calzan con la base (check_schema.py pasa).

Migra la lógica que ya existía en services/ para que lea y escriba en MySQL con
SQLAlchemy. La lógica de negocio NO cambia: solo cambia el acceso a datos y la
eliminación de cualquier dependencia de Flask.

ARCHIVOS
- services/excel_reader.py y services/normalizer.py: no dependen de la base.
  Solo revisa que no importen nada de Flask.
- services/importer.py: guarda en Product y registra cada archivo en Import.
  - Idempotente apoyándose en el índice único (supplier_id, row_hash).
  - Inserta por lotes (bulk) en vez de fila por fila. 5.000 filas en menos de
    10 segundos.
  - Un error en una fila no tumba la importación: se registra en
    rejection_report con número de fila y motivo.
  - Una transacción por importación con rollback limpio si falla lo grueso.
- services/matcher.py, rules_engine.py y consolidator.py: recibe la sesión de base
  como parámetro (Session), no la importes como global. Esto los hace testeables.
  - Los pendientes de revisión se guardan en ProductLink con status 'pending' y las
    razones en la columna reasons.
  - El consolidator crea/actualiza CanonicalProduct y ProductLink de forma
    revertible.

IMPORTANTE
- No migres datos de SQLite. Reimporta los Excel de prueba (tests/fixtures/).
- Cuidado con las comparaciones de texto: la collation utf8mb4_unicode_ci ignora
  mayúsculas y tildes. Verifica que no cause falsas coincidencias donde antes no
  las había.

PRUEBAS
Las que ya existían (precios colombianos, grip rojo agrupado y azul no, reglas,
idempotencia) deben pasar contra MySQL (base stockmind_test).

Verificación: importas fixtures/guerrero.xlsx dos veces y la segunda no duplica
filas; las dos cargas aparecen en la tabla imports.
```

---

## Prompt 6 — Migrar la API a routers FastAPI

```
Lee agent.md. Los servicios ya funcionan sobre MySQL.

Migra todos los endpoints a routers de FastAPI, uno por recurso, en
backend/app/routers/. Mismos recursos y mismas rutas que la API Flask, bajo
/api/v1:

Proveedores:      GET/POST /suppliers, GET/PATCH/DELETE /suppliers/{id}
Importaciones:    POST /imports, GET /imports, GET /imports/{id}
Productos:        GET /products, GET /products/{id}
Catálogo:         GET/POST /canonical-products, GET/PATCH /canonical-products/{id},
                  GET /canonical-products/{id}/suppliers
Coincidencias:    GET /matches/pending, POST /matches/{id}/confirm,
                  POST /matches/{id}/reject, POST /matches/suggest
Reglas:           GET/POST /rules, PATCH/DELETE /rules/{id}
Agente:           (prompt 7)
Reportes:         GET /reports/inventory, GET /reports/price-comparison,
                  GET /reports/purchase-suggestions
Salud:            GET /health

CONVENCIONES (las mismas de siempre)
- Códigos correctos: 200, 201 con Location, 204, 400, 404, 409, 413, 422, 429, 500.
- Éxito {"data", "meta"}; error {"error": {"code", "message", "details"}}.
- Listados paginados con ?page=&per_page= y filtros/orden por query string.
- Cada endpoint declara response_model y los códigos posibles en responses=, para
  que /docs quede completo y sirva de documentación oficial.
- POST /imports recibe UploadFile + supplier_id (Form). Valida extensión (.xlsx),
  tamaño y que el archivo abra. Guarda el original en uploads/ con nombre único.
- Límite de tasa en /imports y en /agent/chat con slowapi.
- Los routers solo traducen HTTP a servicios: sin lógica de negocio ni consultas
  sueltas dentro de los endpoints.

ELIMINA
- docs/openapi.yaml: ya no se mantiene a mano; /docs lo genera.

Entrega además un archivo requests.http con un ejemplo ejecutable por endpoint.

Verificación: todos los endpoints responden desde /docs; los de "no encontrado" y
validación devuelven nuestro formato de error, no el de FastAPI por defecto.
```

---

## Prompt 7 — Migrar el agente

```
Lee agent.md. La API REST ya está en FastAPI.

Migra backend/app/agent/ a la nueva arquitectura. La lógica agéntica NO cambia: el
modelo decide las herramientas, encadena hasta 8 iteraciones y pide confirmación
antes de acciones destructivas. Sin condicionales que adivinen la intención.

CAMBIOS
- tools.py: cada herramienta recibe la sesión de base como parámetro y usa los
  servicios ya migrados. Mantén el esquema JSON de parámetros para tool calling y el
  campo de resumen legible en cada resultado.
- core.py: cada paso se registra en agent_actions (herramienta, parámetros,
  resultado, si requirió confirmación, si fue aprobada, session_id).
- Las acciones destructivas (consolidate) quedan pendientes en agent_actions con
  approved = NULL hasta que POST /agent/confirm las apruebe o rechace. Si pasa
  entre dos peticiones, el estado debe sobrevivir en la base, no en memoria.
- memory.py: el historial por sesión sigue funcionando; si estaba en memoria del
  proceso, déjalo así y documenta la limitación (se pierde al reiniciar).
- Endpoints en routers/agent.py:
  POST /agent/chat, POST /agent/confirm, GET /agent/actions.
- Streaming de la respuesta del agente: soporta stream=true en /agent/chat con
  StreamingResponse (Server-Sent Events), token a token, porque el frontend lo
  muestra así. Los eventos de herramienta (nombre y parámetros) viajan como
  eventos aparte del texto.

Verificación — los tres flujos de siempre deben funcionar de punta a punta:
1. "Acabo de subir la lista de Malusa, dime qué productos se repiten con Guerrero"
2. "Si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo" → regla
   estructurada, confirmación, guardada en equivalence_rules, aplicada
   retroactivamente.
3. "¿A quién me conviene comprar los frenos este mes?"
Después de cada uno, muéstrame las filas nuevas en agent_actions.
```

---

## Prompt 8 — Conectar el frontend

```
Lee agent.md. El backend FastAPI está completo.

Ajusta el frontend para hablar con FastAPI. Solo toca frontend/assets/js/ y lo
mínimo necesario en el HTML. No rediseñes nada.

1. api.js: una sola constante BASE_URL (http://localhost:8000/api/v1) y todas las
   llamadas pasan por una única función request(). Esa función:
   - Distingue tres casos y muestra un mensaje distinto en español para cada uno:
     a) fallo de red ("No se pudo conectar con el servidor. ¿Está encendido el
        backend?"),
     b) respuesta con error {"error": {...}} (muestra message y details),
     c) respuesta que no es JSON.
   - Devuelve data y meta ya desempaquetados.
   - Nunca deja un fetch sin catch.
2. Streaming del agente: consume el SSE de /agent/chat con fetch + ReadableStream
   (no EventSource, porque necesitamos POST) y pinta los tokens a medida que llegan.
3. La importación sigue mostrando progreso: si el backend no reporta avance por
   fila, muestra progreso por etapa (subiendo, leyendo, normalizando, guardando) y
   dímelo para decidir si hace falta un endpoint de estado.
4. Servir el frontend: documenta cómo abrirlo con un servidor local
   (python -m http.server 5500 dentro de frontend/, o Live Server) y NO con doble
   clic. Confirma que el origen usado está en CORS_ORIGINS.

Verificación: recorre las seis pantallas y confirma que ninguna lanza "Failed to
fetch". Apaga el backend a propósito y confirma que cada pantalla muestra el
mensaje de "backend apagado", no una pantalla en blanco.
```

---

## Prompt 9 — Pruebas y verificación final

```
Lee agent.md. El sistema funciona de punta a punta sobre FastAPI + MySQL.

PRUEBAS
- Fixtures de pytest que usen la base stockmind_test, limpien entre pruebas y usen
  TestClient de FastAPI con la dependencia get_db sobrescrita.
- Cobertura sobre app/services/ y app/agent/tools.py por encima del 70%.
- Pruebas de integración por endpoint: caso feliz, no encontrado y validación.
- Las pruebas de siempre: precios colombianos, grip rojo sí / azul no,
  interpretación de regla dictada, idempotencia de reimportación.

DEMO
- Reaplica demo/seed.py contra MySQL: debe cargar los cuatro Excel de proveedores y
  dejar el sistema listo para mostrar.

DOCUMENTACIÓN
- README.md actualizado: instalación desde cero con MySQL (incluyendo el script SQL
  y el .env), cómo levantar backend y frontend, y estructura de carpetas.
- docs/arquitectura.md: actualiza el diagrama (FastAPI, MySQL) y la sección de por
  qué esto es un entorno agéntico.
- Elimina cualquier mención a Flask y SQLite.

VERIFICACIÓN FINAL
Clona el proyecto en una carpeta limpia, crea la base con el script SQL, sigue el
README al pie de la letra y confirma que levanta sin un solo paso no documentado.
Si algo falla, arregla el README.
```

---

## Notas de ejecución

**Una conversación por prompt**, y `git commit` después de cada uno
(`git commit -m "F3: esqueleto FastAPI"`). Si el prompt 6 rompe algo del 5, vas a
querer poder devolverte.

**No subas el `.env` ni la clave de MySQL a GitHub.** Solo `.env.example`, sin
valores.

**Si algo falla con la conexión**, el orden de revisión es: MySQL está corriendo
(panel de XAMPP) → `check_db.py` → usuario y clave del `.env` → recién ahí el código.

**Mantén los puertos claros:** MySQL 3306, FastAPI 8000, frontend 5500. La mayoría
de los "Failed to fetch" salen de un puerto u origen que no coincide.
