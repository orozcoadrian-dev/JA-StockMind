# StockMind

StockMind es un agente de inventario para un almacén de repuestos de moto en Cartagena. Los proveedores envían listas Excel con códigos, columnas y nombres distintos; por eso el mismo repuesto puede aparecer como `GRIP ROJO DEPORTIVO`, `Manubrio grip rojo` o `GRIPS ROJ. UNIV.`. El sistema conserva cada fila original, normaliza el nombre y calcula equivalencias con razones legibles.

El flujo combina automatización y control humano: importa archivos, propone vínculos entre proveedores, permite confirmar o rechazar coincidencias, aprende reglas estructuradas y deja cada cambio auditado. El agente decide qué herramienta encadenar, pero nunca ejecuta una consolidación destructiva sin confirmación.

## Requisitos

- Python 3.11 o superior
- Navegador moderno
- PowerShell en Windows o shell compatible en Linux/macOS

## Instalación limpia

Desde la raíz `03-Src`:

### Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r Backend/requirements.txt
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r Backend/requirements.txt
```

No se necesita una clave LLM para ejecutar importaciones, equivalencias, reportes o pruebas. Para activar chat con un proveedor OpenAI-compatible, define `LLM_API_KEY` y opcionalmente `LLM_API_URL` y `LLM_MODEL`.

## Datos de demostración

Genera cuatro listas realistas y carga sus productos en SQLite:

```bash
python demo/seed.py
```

El script produce:

- `demo/guerrero_demo.xlsx`
- `demo/malusa_demo.xlsx`
- `demo/distrimotos_demo.xlsx`
- `demo/partes_caribe_demo.xlsx`

Cada archivo contiene 85 filas, encabezados en posiciones diferentes, nombres de columnas distintos, precios colombianos, filas vacías, un subtotal y productos exclusivos. Los cuatro incluyen el grip rojo bajo nombres distintos; también hay grip azul y grip rojo de 28 mm.

El seed es idempotente: una segunda ejecución no duplica productos y recalcula las sugerencias pendientes.

## Ejecutar el sistema

Terminal 1, backend:

```bash
python -m uvicorn Backend.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, frontend:

```bash
python -m http.server 5501 --directory Frontend
```

Abre `http://127.0.0.1:5501`. Si el puerto está ocupado, usa otro y agrégalo a `allow_origins` en `Backend/app.py`.

La documentación interactiva está en `http://127.0.0.1:8000/api/docs`. También hay ejemplos listos para REST Client en [docs/api.http](docs/api.http).

## Pruebas y cobertura

Suite completa:

```bash
python -m unittest discover -s Backend/Tests -v
```

Cobertura de servicios y herramientas:

```bash
python -m coverage erase
python -m coverage run --source=Backend/Services,Backend/Agent -m unittest discover -s Backend/Tests
python -m coverage report -m
```

Para ver específicamente las herramientas del agente:

```bash
python -m coverage report -m Backend/Agent/tools.py
```

La medición validada entrega 87% en `Backend/Agent/tools.py` y 82% en el conjunto de servicios y agente. Las pruebas cubren contratos, precios colombianos, normalización, importación idempotente, equivalencias rojo/azul/medida, reglas naturales, confirmación retroactiva, herramientas, API REST y datos demo.

## Estructura

```text
03-Src/
├── Backend/
│   ├── Agent/       loop, memoria, prompt y herramientas
│   ├── Api/         rutas legacy, agente, matches y REST v1
│   ├── Models/      entidades SQLAlchemy y contratos Pydantic
│   ├── Services/    Excel, normalización, matcher y consolidación
│   └── Tests/       pruebas unitarias y de integración
├── demo/            seed.py y cuatro Excel de demostración
├── docs/            contratos, arquitectura, OpenAPI, guion y requests
├── Frontend/        HTML, CSS y JavaScript sin framework
└── agent.md         contexto operativo del proyecto
```

## API canónica

Todas las rutas nuevas usan `/api/v1` y respuestas `{ "data": ..., "meta": ... }`:

- `/suppliers`: proveedores y CRUD.
- `/imports`: carga e historial de archivos.
- `/products`: productos crudos normalizados.
- `/canonical-products`: catálogo consolidado.
- `/matches`: sugerencias pendientes, confirmación y rechazo.
- `/rules`: reglas de equivalencia.
- `/agent`: chat, confirmaciones y auditoría.
- `/reports`: inventario, precios y compras.

Los errores usan `{ "error": { "code", "message", "details" } }`. Las rutas `/api/...` anteriores se conservan como aliases legacy.

## Flujo recomendado para la sustentación

1. Ejecutar `python demo/seed.py`.
2. Abrir el panel y mostrar que el catálogo parte de datos persistidos.
3. Revisar coincidencias y explicar por qué el grip rojo coincide y el azul no.
4. Importar una lista adicional desde la pantalla de importación.
5. Pedir al agente una comparación de proveedores.
6. Dictar una regla y mostrar su confirmación antes de aplicarla.
7. Abrir reportes y cerrar con una sugerencia de compra basada en stock real.

La explicación ampliada está en [docs/arquitectura.md](docs/arquitectura.md) y el guion cronometrado en [docs/demo.md](docs/demo.md).
