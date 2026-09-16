# MotoStock — Prompts de construcción del agente

Proyecto: agente de IA para consolidar inventario de repuestos de moto a partir de
listas de precios en Excel de varios proveedores.

---

## Situación-contexto del parcial

Un almacén de repuestos de moto en Cartagena compra a cuatro o cinco proveedores
mayoristas (Inversiones Guerrero, Malusa, Distrimotos, Partes del Caribe). Cada uno
manda su lista de precios en Excel, cada mes, con su propio formato: columnas
distintas, códigos internos distintos y nombres escritos a mano por quien digitó.

El mismo repuesto aparece como `GRIP ROJO DEPORTIVO`, `Manubrio grip rojo`,
`GRIPS ROJ. UNIV.` y `grip rojo x par` en cuatro archivos distintos, con cuatro
códigos distintos y cuatro precios distintos. Nadie en el almacén sabe con certeza
cuántos grips rojos hay en bodega ni a quién conviene comprarlos.

El dueño sí sabe las equivalencias — las tiene en la cabeza. Lo que no tiene es
tiempo de cruzarlas archivo por archivo.

**Lo que hace el agente:** recibe los Excel, normaliza los productos, propone
equivalencias entre proveedores, aprende las reglas que el dueño le dicta en
lenguaje natural ("si un grip rojo lo provee Guerrero y Malusa, es el mismo"), y a
partir de eso sugiere decisiones: consolidar stock duplicado, a qué proveedor
comprar cada referencia, qué está sobrestockeado y qué está por agotarse.

Esto es un entorno agéntico real y no un chatbot: el agente tiene herramientas
(leer archivo, consultar catálogo, crear regla, calcular equivalencia, generar
reporte), decide cuáles usar, y sus decisiones cambian el estado del sistema.

---

## Orden de ejecución

Ejecuta un prompt por conversación o por sesión de trabajo. No los mezcles: cada
uno asume que el anterior ya quedó funcionando.

| # | Prompt | Qué deja listo | Cómo verificas antes de seguir |
|---|--------|----------------|-------------------------------|
| 0 | Contexto maestro | `agent.md` en la raíz | El archivo existe y describe el dominio |
| 1 | Esqueleto Flask | Servidor que levanta | `python app.py` → responde `/api/health` |
| 2 | Esquemas JSON | Modelos y contratos de datos | Los JSON de ejemplo validan |
| 3 | Ingesta de Excel | Subir y normalizar archivos | Subes un `.xlsx` y ves productos normalizados |
| 4 | Motor de equivalencias | Agrupación de productos | Detecta el caso del grip rojo |
| 5 | Agente IA | Herramientas y loop | Le dictas una regla y la aplica |
| 6 | API REST | Endpoints completos | Todos responden desde Postman o curl |
| 7 | Frontend | Interfaz Kawasaki | Flujo completo desde el navegador |
| 8 | Pruebas y documentación | Entregable del parcial | README + datos de prueba + tests |

**Por qué este orden.** El frontend va casi al final a propósito: si lo construyes
primero terminas rehaciendo pantallas cada vez que cambia el contrato de la API. Y
el motor de equivalencias (4) va antes que el agente (5) porque el agente necesita
que esa función ya exista para poder llamarla como herramienta.

---

## Prompt 0 — Contexto maestro

> Ejecútalo primero, en la raíz del proyecto. Lo que genere se queda en `agent.md`
> y lo lee tu asistente de código en todas las sesiones siguientes.

```
Vas a acompañarme a construir un proyecto completo. Antes de escribir código,
necesito que dejes escrito el contexto del proyecto en un archivo agent.md en la
raíz, para que lo leas al inicio de cada sesión.

DOMINIO
Almacén de repuestos de moto en Cartagena, Colombia. Compra a varios proveedores
mayoristas: Inversiones Guerrero, Malusa, Distrimotos, Partes del Caribe. Cada
proveedor envía mensualmente una lista de precios en Excel con formato propio:
columnas distintas, códigos internos distintos, y nombres de producto digitados a
mano sin estandarizar.

PROBLEMA
El mismo repuesto físico aparece con nombres y códigos distintos en cada lista.
Ejemplo real: "GRIP ROJO DEPORTIVO" (Guerrero, cód. IG-4471),
"Manubrio grip rojo" (Malusa, cód. ML-0892), "GRIPS ROJ. UNIV." (Distrimotos).
Son el mismo producto. El sistema debe poder saberlo.

QUÉ CONSTRUIMOS
Un agente de IA que:
1. Recibe archivos Excel de proveedores y normaliza sus productos a un catálogo único.
2. Propone equivalencias entre productos de proveedores distintos, con un puntaje
   de confianza y la razón de la propuesta.
3. Aprende reglas que el usuario le dicta en lenguaje natural y las convierte en
   reglas estructuradas persistidas. Ejemplo de regla dictada:
   "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo".
4. Con ese catálogo consolidado, sugiere decisiones: a qué proveedor comprar cada
   referencia, qué stock está duplicado en bodega bajo dos códigos, qué está
   sobrestockeado, qué está por agotarse.

ESTO ES UN ENTORNO AGÉNTICO, NO UN CHATBOT
El agente tiene herramientas ejecutables y decide cuáles usar según la petición.
Sus acciones cambian el estado del sistema. Debe poder encadenar varias
herramientas en un turno, explicar qué hizo, y pedir confirmación antes de
cualquier acción destructiva.

STACK
- Backend: Python 3.11 + Flask
- Datos: SQLite vía SQLAlchemy
- Excel: pandas + openpyxl
- API: REST con JSON
- Frontend: HTML + CSS + JavaScript sin framework (fetch contra la API)
- Agente: llamadas a un LLM con tool calling

REGLAS DE TRABAJO
- Español en interfaz, comentarios y mensajes de error. Nombres de variables,
  funciones y archivos en inglés.
- Sin claves ni secretos en el código: todo por variables de entorno.
- Nada de datos inventados en la interfaz: si no hay datos, se muestra estado vacío.
- Cada función que toque dinero o inventario lleva su prueba.

TAREA
Escribe agent.md con toda esta información, más una sección "Estado del proyecto"
que iremos actualizando, y una sección "Decisiones tomadas" para registrar por qué
elegimos cada cosa. No escribas código todavía.
```

---

## Prompt 1 — Esqueleto del backend Flask

```
Lee agent.md antes de empezar.

Crea la estructura base del backend. Estructura exacta:

backend/
├── app.py                  # factory de Flask, registro de blueprints, nada más
├── config.py               # configuración por entorno, lee de .env
├── requirements.txt
├── .env.example            # variables sin valores reales
├── database.py             # instancia de SQLAlchemy e init
├── models/
│   └── __init__.py
├── api/
│   └── __init__.py
├── services/
│   └── __init__.py
├── agent/
│   └── __init__.py
├── uploads/                # Excel recibidos, ignorado por git
└── tests/
    └── test_health.py

REQUISITOS
- app.py usa el patrón application factory: create_app(config_name).
- config.py define DevelopmentConfig, TestingConfig y ProductionConfig. Lee
  SECRET_KEY, DATABASE_URL, LLM_API_KEY y MAX_UPLOAD_MB del entorno. En desarrollo
  cae a valores por defecto seguros; en producción falla ruidosamente si faltan.
- CORS habilitado solo para el origen del frontend.
- Manejadores de error globales que devuelven JSON, nunca HTML: 400, 404, 413
  (archivo muy grande), 422 (validación) y 500. Formato:
  {"error": {"code": "...", "message": "...", "details": {...}}}
- Un blueprint api/health.py con GET /api/health que devuelve estado, versión y si
  la base responde.
- Logging a consola y a archivo, con nivel configurable.
- requirements.txt con versiones fijadas.
- .gitignore con __pycache__/, .env, venv/, *.db, uploads/*

ENTREGABLE
La estructura creada, más las instrucciones exactas para crear el entorno virtual,
instalar y levantar el servidor en Windows y en Linux. Al final actualiza la
sección "Estado del proyecto" de agent.md.
```

---

## Prompt 2 — Esquemas JSON y modelos de datos

```
Lee agent.md. El esqueleto Flask ya está funcionando.

Define el modelo de datos y los contratos JSON del sistema. Esta es la pieza más
importante del proyecto: todo lo demás depende de que estas estructuras estén bien.

ENTIDADES

Supplier: id, nombre, nit, contacto, activo, fecha de creación.

Product (producto tal como lo manda el proveedor, sin tocar): id, supplier_id,
código del proveedor, nombre crudo tal cual venía en el Excel, nombre normalizado,
categoría, precio unitario, moneda, unidad de medida, cantidad por empaque, fecha
de la lista de precios, hash de la fila original.

CanonicalProduct (el producto real, unificado): id, nombre canónico, categoría,
atributos como JSON (color, medida, marca compatible, etc.), stock en bodega,
stock mínimo, fecha de creación.

ProductLink (une un Product con su CanonicalProduct): id, product_id,
canonical_product_id, confianza de 0 a 1, origen del vínculo (regla, sugerencia
del agente, confirmación manual), quién lo confirmó, fecha.

EquivalenceRule (las reglas que dicta el usuario): id, texto original dictado por
el usuario, condición estructurada como JSON, proveedores involucrados, activa,
fecha, veces aplicada.

AgentAction (bitácora de todo lo que hace el agente): id, timestamp, herramienta
usada, parámetros de entrada, resultado, si requirió confirmación, si fue aprobada.

FORMATO DE LA REGLA ESTRUCTURADA
Cuando el usuario dicta "si un grip rojo lo provee Inversiones Guerrero y Malusa,
es el mismo", la condición estructurada debe quedar algo así:

{
  "type": "supplier_equivalence",
  "match": {
    "keywords": ["grip", "rojo"],
    "attributes": {"color": "rojo", "tipo": "grip"}
  },
  "suppliers": ["Inversiones Guerrero", "Malusa"],
  "action": "merge_to_canonical",
  "confidence": 1.0
}

Diseña este esquema tú con criterio: debe soportar al menos reglas de equivalencia
entre proveedores, reglas de exclusión ("estos dos NO son el mismo aunque se
parezcan") y reglas de preferencia de compra ("para frenos, prefiere Distrimotos").

TAREA
1. Modelos SQLAlchemy en backend/models/, un archivo por entidad.
2. Esquemas de validación con Marshmallow o Pydantic en backend/models/schemas.py,
   separando entrada y salida.
3. Un archivo docs/contratos.md con cada estructura JSON de ejemplo, comentada.
4. Migración inicial o script de creación de tablas con datos semilla: los cuatro
   proveedores y tres categorías.
5. Pruebas que validen que un JSON correcto pasa y varios incorrectos fallan con
   mensaje claro.

Los índices importan: vamos a buscar mucho por nombre normalizado y por supplier_id.
```

---

## Prompt 3 — Ingesta y normalización de Excel

```
Lee agent.md y docs/contratos.md.

Construye el módulo que recibe archivos Excel de proveedores y los convierte en
productos normalizados. El problema real es que cada proveedor manda un formato
distinto y el módulo tiene que arreglárselas.

CASOS QUE DEBE MANEJAR
- Columnas con nombres distintos: "Código" / "Cod." / "REFERENCIA" / "SKU" todas
  significan lo mismo. Igual con descripción, precio, unidad, existencia.
- Filas de basura arriba del encabezado real: logo, título, fecha, filas vacías.
- Precios como texto: "$ 12.500", "12.500,00", "12500", "  12500  ".
- Celdas combinadas, filas totalmente vacías, filas de subtotal en medio.
- Nombres sucios: mayúsculas, abreviaturas, tildes inconsistentes, espacios dobles.

QUÉ CONSTRUIR

1. services/excel_reader.py
   - Detecta automáticamente la fila del encabezado real.
   - Mapea columnas a campos canónicos con un diccionario de sinónimos ampliable,
     y coincidencia difusa para lo que no esté en el diccionario.
   - Si no logra mapear una columna obligatoria, no adivina: devuelve el problema
     para que el usuario mapee a mano.
   - Devuelve filas crudas más un reporte de qué entendió y qué descartó.

2. services/normalizer.py
   - normalize_name(): minúsculas, sin tildes, sin puntuación redundante, espacios
     colapsados, abreviaturas expandidas con un diccionario del rubro (univ →
     universal, del → delantero, tras → trasero, roj → rojo, x par → par).
   - extract_attributes(): saca color, medida, lado, marca compatible y tipo de
     repuesto del nombre, y los devuelve como diccionario.
   - parse_price(): convierte cualquiera de los formatos de arriba a Decimal.
     Ojo con el formato colombiano: el punto es separador de miles.

3. services/importer.py
   - Orquesta: leer, normalizar, validar contra el esquema, guardar en Product.
   - Detecta filas duplicadas dentro del mismo archivo por hash.
   - Es idempotente: reimportar el mismo archivo no duplica datos, actualiza.
   - Devuelve un resumen: filas leídas, importadas, actualizadas, rechazadas con
     su motivo y número de fila.

4. Endpoint POST /api/imports con multipart/form-data: archivo + supplier_id.
   Valida extensión, tamaño y que el archivo abra. Devuelve el resumen.

RESTRICCIONES
- Un archivo de 5.000 filas debe procesarse en menos de 10 segundos.
- Ningún error de una fila puede tumbar la importación completa.
- El archivo original se guarda en uploads/ con nombre único y se registra su ruta.

Genera también dos Excel de ejemplo en tests/fixtures/, uno de Guerrero y uno de
Malusa, con formatos deliberadamente distintos y ambos conteniendo un grip rojo
escrito de forma diferente. Escribe pruebas usando esos archivos.
```

---

## Prompt 4 — Motor de equivalencias

```
Lee agent.md. Ya tenemos productos importados y normalizados de varios proveedores.

Construye el motor que decide si dos productos de proveedores distintos son el
mismo producto físico. Esta es la lógica central del proyecto.

services/matcher.py

find_candidates(product) -> lista de (canonical_product, score, reasons)
Combina varias señales, cada una con su peso:
- Similitud del nombre normalizado (token_set_ratio o similar).
- Coincidencia de atributos extraídos: color, medida, tipo, lado. Un atributo que
  coincide suma; uno que contradice debe penalizar fuerte, no solo no sumar. Un
  grip rojo y un grip azul comparten casi todo el nombre y no son el mismo.
- Cercanía de precio dentro de un rango razonable entre proveedores.
- Misma categoría.

Devuelve siempre las razones en texto legible, no solo el número. El usuario tiene
que poder entender por qué el sistema cree que son el mismo.

Umbrales: sobre 0.90 se propone vínculo automático; entre 0.65 y 0.90 queda
pendiente de revisión humana; bajo 0.65 se descarta.

services/rules_engine.py
- apply_rules(product): evalúa las EquivalenceRule activas contra un producto.
- Una regla que coincide gana sobre el puntaje calculado: si el usuario dijo que
  son el mismo, son el mismo, aunque el algoritmo puntúe bajo.
- Las reglas de exclusión ganan sobre todo lo demás.
- Registra en la regla cuántas veces se aplicó.
- Detecta conflictos entre reglas y los reporta en vez de resolverlos en silencio.

services/consolidator.py
- Crea o actualiza CanonicalProduct y sus ProductLink.
- Al fusionar, el nombre canónico se elige con criterio: el más completo y legible
  de los candidatos, no simplemente el primero.
- Nunca fusiona sin dejar rastro: todo queda revertible desde ProductLink.

Endpoints:
- POST /api/matches/suggest — recalcula sugerencias pendientes
- GET  /api/matches/pending — lista lo que espera revisión humana, con razones
- POST /api/matches/{id}/confirm — confirma un vínculo
- POST /api/matches/{id}/reject — lo rechaza y opcionalmente crea regla de exclusión

PRUEBA OBLIGATORIA
Con los fixtures del prompt anterior, el motor debe agrupar el grip rojo de
Guerrero con el de Malusa, y NO agruparlo con un grip azul ni con un grip rojo de
otra medida. Escribe esa prueba explícitamente.
```

---

## Prompt 5 — El agente de IA

```
Lee agent.md. El motor de equivalencias ya funciona como función de Python.
Ahora envolvemos todo en un agente que decide por su cuenta qué ejecutar.

backend/agent/

tools.py — las herramientas ejecutables, cada una con su esquema JSON de
parámetros para tool calling:
- import_excel(file_id, supplier_id)
- search_products(query, supplier_id?, category?)
- get_canonical_product(id)
- suggest_matches(product_id?)
- create_equivalence_rule(natural_text) → interpreta el texto y devuelve la regla
  estructurada para que el usuario la confirme antes de guardarla
- list_rules()
- consolidate(product_ids, canonical_name) → DESTRUCTIVA, exige confirmación
- get_inventory_report(filters)
- compare_supplier_prices(canonical_product_id)
- get_purchase_suggestions(budget?, categories?)

Cada herramienta valida sus parámetros, maneja sus errores y devuelve JSON
estructurado con un campo de resumen legible.

prompts.py — el system prompt del agente. Debe contener el contexto del negocio,
las reglas activas del usuario resumidas, la instrucción de encadenar herramientas
cuando haga falta, la obligación de pedir confirmación antes de cualquier acción
destructiva, y la prohibición de inventar datos: si una herramienta no devolvió
algo, el agente lo dice.

core.py — el loop del agente:
- Recibe mensaje del usuario más historial.
- Llama al LLM con las herramientas disponibles.
- Si el modelo pide herramientas, las ejecuta, mete los resultados en el historial
  y vuelve a llamar. Máximo 8 iteraciones, con corte limpio si se pasa.
- Registra cada paso en AgentAction.
- Devuelve respuesta final, lista de herramientas usadas y acciones pendientes de
  confirmación.

memory.py — historial de conversación por sesión, con resumen automático cuando
se pasa del límite de contexto.

Endpoints:
- POST /api/agent/chat — mensaje del usuario, respuesta del agente
- POST /api/agent/confirm — aprueba o rechaza una acción pendiente
- GET  /api/agent/actions — bitácora

FLUJOS QUE DEBEN FUNCIONAR DE PUNTA A PUNTA
1. "Acabo de subir la lista de Malusa, dime qué productos se repiten con Guerrero"
   → busca, sugiere coincidencias, presenta con razones, no fusiona sin permiso.
2. "Si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo"
   → interpreta, muestra la regla estructurada, pide confirmación, la guarda, la
   aplica retroactivamente y reporta cuántos productos afectó.
3. "¿A quién me conviene comprar los frenos este mes?"
   → compara precios entre proveedores de los productos canónicos de esa categoría
   y sustenta la recomendación con números.

La clave del parcial está aquí: el agente decide la secuencia, no la trae fija.
No escribas condicionales que adivinen la intención del usuario — deja que el
modelo elija las herramientas.
```

---

## Prompt 6 — API REST completa

```
Lee agent.md. Todos los servicios funcionan. Ahora consolidamos la API REST
completa, coherente y documentada.

Revisa los endpoints que ya existen y refactorízalos para que todos sigan las
mismas convenciones. Luego completa lo que falte.

CONVENCIONES OBLIGATORIAS
- Recursos en plural, sustantivos, sin verbos en la URL.
- Verbos HTTP correctos: GET lee, POST crea, PUT reemplaza, PATCH modifica parcial,
  DELETE borra.
- Códigos correctos: 200, 201 con Location, 204, 400, 404, 409 en conflicto, 413,
  422 en validación, 429 si limitas tasa, 500.
- Toda respuesta es JSON. Éxito: {"data": ..., "meta": ...}.
  Error: {"error": {"code", "message", "details"}}.
- Listados siempre paginados: ?page=&per_page= con meta de total y páginas.
- Filtros y orden por query string: ?supplier_id=&category=&sort=-price
- Versionado en la ruta: /api/v1/...

SUPERFICIE COMPLETA
Proveedores:      GET/POST /suppliers, GET/PATCH/DELETE /suppliers/{id}
Importaciones:    POST /imports, GET /imports, GET /imports/{id}
Productos:        GET /products, GET /products/{id}
Catálogo:         GET/POST /canonical-products, GET/PATCH /canonical-products/{id},
                  GET /canonical-products/{id}/suppliers
Coincidencias:    GET /matches/pending, POST /matches/{id}/confirm,
                  POST /matches/{id}/reject, POST /matches/suggest
Reglas:           GET/POST /rules, PATCH/DELETE /rules/{id}
Agente:           POST /agent/chat, POST /agent/confirm, GET /agent/actions
Reportes:         GET /reports/inventory, GET /reports/price-comparison,
                  GET /reports/purchase-suggestions
Salud:            GET /health

ADEMÁS
- Documentación OpenAPI 3 en docs/openapi.yaml y servida en /api/docs.
- Colección de Postman o archivo .http con todos los endpoints y ejemplos reales
  listos para ejecutar.
- Pruebas de integración de cada endpoint: caso feliz, no encontrado y validación.
- Límite de tasa en /agent/chat y en /imports.

No rompas nada de lo que ya funcionaba: si cambias una ruta, actualiza también
quien la consume.
```

---

## Prompt 7 — Frontend

```
Lee agent.md. La API está completa y documentada en docs/openapi.yaml.

Construye la interfaz web. HTML, CSS y JavaScript puro, sin frameworks ni librerías
de componentes.

IDENTIDAD VISUAL
Paleta de motos Kawasaki. Verde lima como color de marca, negro y grafito como
base, blanco hueso para superficies de trabajo:

  --verde       #6CB33F   acento de marca, uso deliberado y escaso
  --verde-hondo #4A8A2A   estados activos, hover
  --negro       #101010   navegación, encabezados
  --grafito     #2B2E2C   texto principal sobre claro
  --hueso       #F3F4F0   fondo de las áreas de datos
  --alerta      #C9282D   stock crítico, conflictos

El verde es acento, no fondo. Una interfaz de inventario se usa horas seguidas:
verde lima a pantalla completa cansa la vista y hunde la legibilidad de las tablas.
Fondo claro en las zonas de trabajo, barra y encabezados en negro, verde reservado
para la acción principal de cada pantalla, estados activos y datos destacados.

Temática moto sin caer en calcomanías: la referencia es el manual de taller y la
tabla de despiece, no el afiche de carreras. Tipografía condensada e industrial
para titulares y datos numéricos; una sans neutra y legible para el cuerpo.
Diagonales sutiles del ángulo del carenado en separadores, no en todas partes.
Sin logos ni marcas registradas de Kawasaki: es la paleta, no la marca.

DINAMISMO
El movimiento responde a acciones del usuario y muestra qué cambió:
- Barra de progreso real durante la importación del Excel, fila por fila.
- Cuando el agente fusiona productos, las dos filas se acercan y se funden en una.
- Los mensajes del agente llegan en streaming, token a token.
- Contadores que transicionan al cambiar, no que saltan.
Nada de animaciones de entrada en cada tarjeta al hacer scroll. Respeta
prefers-reduced-motion.

PANTALLAS

index.html — Panel
Lo primero que se ve es el estado real del inventario consolidado: cuántos
productos únicos, cuántos siguen sin consolidar, cuántas coincidencias esperan
revisión, cuánto capital hay en bodega. Accesos a subir lista y abrir el agente.

importar.html — Subir lista de proveedor
Zona de arrastrar y soltar, selección de proveedor, vista previa de las primeras
filas con el mapeo de columnas que el sistema entendió y opción de corregirlo antes
de confirmar. Progreso durante el proceso. Resumen al terminar, con las filas
rechazadas y su motivo.

inventario.html — Catálogo consolidado
Tabla densa de productos canónicos. Cada fila expande para mostrar de qué
proveedores viene y a qué precio cada uno, con el más barato destacado. Búsqueda
instantánea, filtros por proveedor y categoría, orden por columna. Aquí la
densidad de información importa más que el aire.

coincidencias.html — Revisión de equivalencias
Comparación lado a lado de los dos productos candidatos con sus atributos
alineados, el puntaje y las razones en texto. Botones de confirmar y rechazar.
Atajos de teclado, porque se revisan muchas seguidas.

agente.html — Conversación
Chat con el agente. Cuando ejecuta una herramienta, se ve cuál y con qué
parámetros, colapsable. Las acciones destructivas aparecen como tarjeta de
confirmación dentro de la conversación, no como alert del navegador.

reportes.html — Reportes
Comparación de precios por proveedor, sugerencias de compra, stock crítico.
Exportable a Excel.

ORGANIZACIÓN
frontend/
├── index.html
├── pages/          las demás pantallas
└── assets/
    ├── css/        tokens.css, base.css, components.css, una hoja por pantalla
    └── js/
        ├── api.js      todas las llamadas fetch, en un solo lugar
        ├── ui.js       helpers compartidos: toast, modal, formato de moneda
        └── una por pantalla

CALIDAD
Responsive hasta móvil. Foco de teclado visible. Contraste AA. Estados de carga,
vacío y error en cada pantalla — el estado vacío dice qué hacer, no solo que no
hay nada. Moneda en formato colombiano. Nada de datos de ejemplo quemados en el
HTML: todo sale de la API.
```

---

## Prompt 8 — Pruebas, datos y entrega

```
Lee agent.md. El sistema funciona de punta a punta. Prepara la entrega del parcial.

DATOS DE DEMOSTRACIÓN
Genera cuatro Excel realistas en demo/, uno por proveedor, con formatos claramente
distintos entre sí: encabezados en filas diferentes, nombres de columna distintos,
precios en formatos distintos. Entre 80 y 150 filas cada uno, con productos reales
de repuestos de moto. Tienen que contener a propósito:
- El grip rojo bajo cuatro nombres y códigos diferentes.
- Un grip azul y un grip rojo de otra medida, para probar que NO se fusionan.
- Productos exclusivos de un solo proveedor.
- Filas sucias: precios como texto, filas vacías, un subtotal en medio.

Y un script demo/seed.py que cargue todo y deje el sistema listo para mostrar.

PRUEBAS
Cobertura sobre services/ y agent/tools.py por encima del 70%. Que incluya las de
normalización de precios colombianos, la de que el grip rojo se agrupa y el azul no,
la interpretación de una regla dictada en lenguaje natural, y la idempotencia de la
reimportación.

DOCUMENTACIÓN
README.md con: el problema en dos párrafos, qué hace el sistema, capturas, cómo
instalarlo y correrlo paso a paso desde cero, y la estructura de carpetas explicada.

docs/arquitectura.md con un diagrama del flujo completo, desde el Excel hasta la
sugerencia de compra, y la explicación de por qué esto es un entorno agéntico:
qué herramientas tiene el agente, cómo decide, qué puede cambiar del sistema y qué
requiere autorización humana.

docs/demo.md con un guion de sustentación de 8 minutos: qué mostrar, en qué orden,
y qué tres frases dictarle al agente en vivo para que se vea decidir.

VERIFICACIÓN FINAL
Clona el proyecto en una carpeta limpia, sigue tu propio README al pie de la letra
y confirma que levanta sin un solo paso no documentado. Si algo falla, arregla el
README, no el recuerdo de lo que había que hacer.
```

---

## Notas de ejecución

**Una conversación por prompt.** Si metes dos en la misma sesión, el asistente
arrastra contexto viejo y empieza a reescribir lo que ya funcionaba.

**Después de cada prompt, haz commit.** `git commit -m "P3: ingesta de Excel"`.
Cuando el prompt 5 rompa algo del 4, vas a querer poder devolverte.

**Revisa antes de avanzar.** La columna de verificación de la tabla de arriba está
para eso. Un error en el prompt 2 sale carísimo en el prompt 7.

**La clave calificable del parcial es el prompt 5.** Ahí está el entorno agéntico:
el agente decide qué herramienta usar, encadena varias, y sus acciones modifican el
estado del sistema. Si terminas escribiendo `if "grip" in mensaje:` en algún lado,
dejaste de tener un agente y volviste a tener un chatbot con reglas.
