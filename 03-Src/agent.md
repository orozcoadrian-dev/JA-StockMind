# agent.md

## Propósito del proyecto
Este repositorio es el contexto operativo y de diseño del proyecto para construir un sistema agéntico de gestión de inventarios y consolidación de repuestos para una empresa de motocicletas en Cartagena, Colombia.

El objetivo es crear un agente de IA que reciba archivos Excel de distintos proveedores, normalice productos, proponga equivalencias entre referencias distintas, aprenda reglas dictadas por el usuario en lenguaje natural, y apoye decisiones de compra, stock y consolidación de inventario.

---

## Dominio
- Almacén de repuestos de moto en Cartagena, Colombia.
- Compra a varios proveedores mayoristas:
  - Inversiones Guerrero
  - Malusa
  - Distrimotos
  - Partes del Caribe
- Cada proveedor envía mensualmente una lista de precios en Excel con formato propio.
- Los archivos suelen tener:
  - columnas distintas,
  - códigos internos distintos,
  - nombres de producto digitados a mano sin estandarizar.

### Ejemplo real del problema
El mismo repuesto físico puede aparecer con nombres y códigos distintos en cada lista, por ejemplo:
- "GRIP ROJO DEPORTIVO" (Guerrero, código IG-4471)
- "Manubrio grip rojo" (Malusa, código ML-0892)
- "GRIPS ROJ. UNIV." (Distrimotos)

Todos estos registros representan el mismo producto físico, pero el sistema actual no lo identifica de forma consistente.

---

## Problema a resolver
Necesitamos un sistema que pueda:
1. identificar que varias referencias de distintos proveedores corresponden al mismo repuesto,
2. consolidar esos productos en un catálogo único,
3. calcular un puntaje de confianza para cada equivalencia propuesta,
4. explicar la razón de la coincidencia,
5. aprender reglas nuevas a partir de instrucciones del usuario en lenguaje natural,
6. sugerir decisiones operativas basadas en inventario, costo, duplicidad y disponibilidad.

---

## Qué construimos
Construiremos un agente de IA con las siguientes capacidades:

1. Recepción de archivos Excel de proveedores y normalización de productos a un catálogo único.
2. Propuesta de equivalencias entre productos de distintos proveedores, con:
   - puntaje de confianza,
   - razón de la propuesta,
   - evidencia relevante por comparación.
3. Aprendizaje de reglas que el usuario dicte en lenguaje natural y conversión de esas reglas en reglas estructuradas persistidas.
   - Ejemplo de regla dictada: "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo".
4. Consolidación del catálogo para apoyar decisiones como:
   - a qué proveedor comprar cada referencia,
   - qué stock está duplicado en bodega bajo dos códigos,
   - qué productos están sobrestockeados,
   - qué productos están por agotarse.

---

## Naturaleza del entorno
Esto es un entorno agéntico, no un chatbot.

El agente debe:
- tener herramientas ejecutables,
- decidir cuáles usar según la petición,
- encadenar varias herramientas en un mismo turno,
- explicar qué hizo,
- pedir confirmación antes de ejecutar cualquier acción destructiva,
- cambiar el estado del sistema mediante sus acciones.

---

## Stack previsto
- Backend: Python 3.11 + Flask
- Datos: SQLite vía SQLAlchemy
- Excel: pandas + openpyxl
- API: REST con JSON
- Frontend: HTML + CSS + JavaScript sin framework (fetch contra la API)
- Agente: llamadas a un LLM con tool calling

---

## Reglas de trabajo
- Español en interfaz, comentarios y mensajes de error.
- Nombres de variables, funciones y archivos en inglés.
- Sin claves ni secretos en el código: todo por variables de entorno.
- Nada de datos inventados en la interfaz: si no hay datos, se muestra estado vacío.
- Cada función que toque dinero o inventario lleva su prueba.

---

## Suposiciones de diseño
- El sistema debe funcionar con datos reales de proveedores, pero su desarrollo puede iniciar con datos de ejemplo controlados.
- La normalización y la comparación semántica pueden apoyarse con reglas del dominio y luego evolucionar hacia uso de embeddings o modelos de lenguaje más robustos.
- La persistencia de reglas debe permitir auditoría y revisión humana.
- La lógica de decisiones debe estar separada de la lógica de presentación.

---

## Estado del proyecto
### Estado actual
- Se ha definido el contexto del dominio y la necesidad del sistema.
- Se identificó el problema principal: duplicidad de registros y falta de estandarización entre proveedores.
- Se estableció la arquitectura base prevista y las tecnologías principales.
- Los contratos, modelos SQLAlchemy, normalización e importación de Excel están implementados.
- El motor de equivalencias está implementado en `Backend/Services/matcher.py`.
- Las reglas activas se evalúan con prioridad de exclusión y conflictos reportables en `Backend/Services/rules_engine.py`.
- La consolidación crea `CanonicalProduct` y `ProductLink`; los vínculos son reversibles mediante `revert_link`.
- Las sugerencias se persisten como `MatchSuggestion` y cuentan con endpoints de sugerencia, pendientes, confirmación y rechazo.
- La prueba obligatoria confirma que el grip rojo de Guerrero y Malusa coincide, pero el grip azul y la medida distinta se descartan.
- El agente agéntico está implementado en `Backend/Agent/`: herramientas validadas, prompt de sistema, memoria por sesión y loop de hasta ocho iteraciones.
- Las herramientas registran cada ejecución en `AgentAction` y las operaciones destructivas esperan confirmación explícita.
- Las reglas creadas por lenguaje natural se muestran estructuradas, esperan confirmación, se persisten y se aplican retroactivamente.
- Los endpoints del agente están disponibles en `/api/agent/chat`, `/api/agent/confirm` y `/api/agent/actions`.
- La API REST versionada está disponible bajo `/api/v1`, con CRUD de proveedores, importaciones, productos, catálogo, reglas, coincidencias, agente y reportes.
- Las respuestas versionadas usan `data/meta` en éxito y `error {code, message, details}` en fallos; los listados incluyen paginación.
- OpenAPI está servido en `/api/docs` y documentado en `docs/openapi.yaml`; los ejemplos ejecutables están en `docs/api.http`.
- Se añadieron rate limits para imports y chat, y pruebas HTTP de 404, 422, 201/Location, 204, PATCH parcial y paginación.
- La interfaz web operativa está implementada en `Frontend/`: panel, importación, inventario, coincidencias, agente y reportes.
- El frontend consume `/api/v1` sin datos simulados, conserva estados vacíos y muestra progreso real al subir archivos.
- Se estableció la identidad visual hueso/grafito/verde, navegación lateral responsive, tabla densa y respeto por `prefers-reduced-motion`.
- La entrega del parcial está preparada: `demo/seed.py` genera cuatro Excel de 85 filas y deja sugerencias listas para mostrar.
- `README.md`, `docs/arquitectura.md` y `docs/demo.md` documentan instalación, arquitectura, flujo agéntico y sustentación.
- La cobertura validada es 87% para `Backend/Agent/tools.py` y 82% para el conjunto de servicios y agente.
- Una copia limpia temporal creó un venv, instaló `Backend/requirements.txt`, ejecutó el seed y pasó las 27 pruebas.

### Siguiente paso
- Entregar y sustentar el parcial.

### Pendiente por actualizar
- No hay bloqueos funcionales pendientes para la entrega.

---

## Decisiones tomadas
- Se eligió Flask como backend porque el proyecto requiere un flujo sencillo, legible y apropiado para un PoC y evolución temprana.
- Se eligió SQLite con SQLAlchemy para facilitar desarrollo rápido, trazabilidad local y persistencia básica sin complejidad de infraestructura.
- Se eligió pandas + openpyxl para manejar archivos Excel de proveedores con formatos distintos.
- Se eligió HTML + CSS + JavaScript sin framework para mantener la interfaz simple, ligera y compatible con fetch directo a la API.
- Se optó por tool calling en el agente para que el sistema pueda ejecutar acciones reales sobre datos y no solo responder con texto.
- Se definió que todos los nombres y archivos en código sean en inglés para mantener una convención clara y consistente.
- Se priorizó la validación de funciones relacionadas con inventario y dinero mediante pruebas, para reducir riesgo operativo.
- Se decidió que la interfaz no muestre datos inventados; cuando no haya información, debe mostrar estado vacío y permitir continuidad.
- Se decidió persistir las sugerencias separadas de los vínculos confirmados: `MatchSuggestion` conserva score, razones y estado; `ProductLink` solo representa la consolidación realizada.
- Se definieron los pesos iniciales del matcher: nombre 0.42, atributos 0.48, precio 0.05 y categoría 0.05. Una contradicción de atributo aplica una penalización fuerte.
- Se definieron los umbrales del matcher: más de 0.90 automático, de 0.65 a 0.90 revisión humana y menos de 0.65 descartado.
- Se decidió usar un cliente LLM compatible con OpenAI inyectable para probar el loop sin depender de una clave real; sin `LLM_API_KEY`, el endpoint devuelve un error explícito de configuración.
- Se decidió que el agente no interpreta la intención mediante condicionales del mensaje: el modelo elige las herramientas y el core solo ejecuta llamadas estructuradas.
- Se decidió introducir `/api/v1` como superficie canónica y conservar las rutas `/api/...` existentes como aliases legacy para no romper consumidores actuales.
- Se decidió persistir cada importación como `ImportRecord` para que los endpoints de listado y detalle no dependan de nombres de archivos en disco.
- Se decidió mantener el frontend como HTML/CSS/JavaScript puro y servirlo localmente en el origen explícito configurado por CORS.
- Se decidió generar los Excel demo desde un script determinista para que la sustentación pueda reconstruirse desde una carpeta limpia.

---

## Notas para futuras sesiones
- Este documento debe leerse al inicio de cada sesión como contexto base del proyecto.
- Cuando se tomen decisiones relevantes, deben registrarse aquí en la sección "Decisiones tomadas".
- Cuando el proyecto avance, actualizar la sección "Estado del proyecto" con cambios reales, avances, bloqueos y próximos pasos.
