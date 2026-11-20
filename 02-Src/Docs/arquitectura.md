# Arquitectura de StockMind

## Flujo completo

```mermaid
flowchart LR
    Excel[Lista Excel del proveedor] --> Reader[excel_reader]
    Reader --> Normalizer[normalizer]
    Normalizer --> Product[(Product)]
    Product --> Matcher[matcher]
    Matcher --> Suggestion[(MatchSuggestion)]
    Suggestion --> Review{Revisión humana}
    Review -->|confirmar| Consolidator[consolidator]
    Review -->|rechazar| Rule[Regla de exclusión opcional]
    Rule --> Rules[EquivalenceRule]
    Rules --> Matcher
    Consolidator --> Canonical[(CanonicalProduct)]
    Consolidator --> Link[(ProductLink reversible)]
    Canonical --> Reports[Reportes de inventario y compra]
    Agent[LLM + tool calling] --> Tools[Herramientas validadas]
    Tools --> Reader
    Tools --> Matcher
    Tools --> Rules
    Tools --> Consolidator
    Tools --> Reports
    Tools --> Audit[(AgentAction)]
```

## Capas

### Persistencia

SQLAlchemy almacena el producto original (`Product`), el catálogo real (`CanonicalProduct`), vínculos (`ProductLink`), sugerencias (`MatchSuggestion`), reglas (`EquivalenceRule`), importaciones (`ImportRecord`) y bitácora del agente (`AgentAction`). El historial conversacional se conserva en `ChatSession` y `ChatMessage`; las preferencias confirmadas viven en `AgentMemoryFact` con referencias a la sesión y al mensaje de origen.

### Servicios

- `excel_reader.py`: detecta encabezado, mapea alias y devuelve filas crudas.
- `normalizer.py`: limpia nombres, extrae atributos y convierte precios colombianos.
- `matcher.py`: combina nombre, atributos, precio y categoría; devuelve score y razones.
- `rules_engine.py`: evalúa reglas activas, prioriza exclusiones y reporta conflictos.
- `consolidator.py`: crea el canónico y los vínculos auditables; permite revertirlos.
- `importer.py`: coordina lectura, validación, idempotencia y persistencia.

### API

La superficie canónica es `/api/v1`; los éxitos usan `data/meta` y los errores un JSON uniforme. Las rutas de sesiones `/agent/sessions` permiten listar, crear, consultar, renombrar, archivar, leer mensajes y exportar. El chat acepta mensajes de hasta 8000 caracteres y session IDs UUID4. `/agent/memory/facts` lista facts con paginación y estado; `PATCH /agent/memory/facts/{id}` solo los deshabilita.

## Por qué es un entorno agéntico

No hay un router que decida según palabras como `grip` o `freno`. El agente recibe el mensaje y el historial, entrega al LLM el catálogo de herramientas y ejecuta los `tool_calls` que el modelo solicita, hasta ocho iteraciones. Cada resultado vuelve al historial para que el modelo decida el siguiente paso.

Las herramientas disponibles son:

- importar Excel;
- buscar productos;
- consultar catálogo canónico;
- sugerir equivalencias;
- interpretar reglas naturales;
- listar reglas;
- consolidar productos;
- generar inventario;
- comparar precios;
- sugerir compras;
- guardar una preferencia estable con confirmación (`remember_fact`);
- consultar preferencias activas (`list_memory_facts`).

El agente puede cambiar el estado mediante importaciones, reglas confirmadas y consolidaciones aprobadas. Las acciones destructivas no se ejecutan desde el primer `tool_call`: devuelven `confirmation_required`, se registran en `AgentAction` y esperan `POST /api/v1/agent/confirm`. Si el usuario rechaza, se registra la decisión y no se modifica el catálogo.

Las preferencias confirmadas se añaden al contexto como un bloque `system` de hasta 20 facts. Al superar `AGENT_SUMMARY_THRESHOLD` (60 por defecto) mensajes desde el resumen previo, el agente guarda otro resumen `system`; los mensajes fuente permanecen intactos y no se vuelven a enviar al LLM. `GET /api/v1/agent/memory/facts` lista los facts y `PATCH /api/v1/agent/memory/facts/{id}` los deshabilita sin borrarlos. `AGENT_MEMORY_MAX_MESSAGES` controla el tamaño del contexto reciente (30 por defecto).

Los IDs UUID4 dificultan la enumeración, pero no reemplazan la autenticación. La API aún no asigna propietario a sesiones ni facts y el listado de sesiones es global; no debe exponerse a clientes no confiables hasta añadir autenticación y autorización por propietario. El frontend renderiza contenido mediante `textContent`; el contenido histórico continúa siendo no confiable para las instrucciones del LLM.

## Decisiones y trazabilidad

El matcher penaliza contradicciones de atributos con fuerza: un grip rojo y uno azul no se convierten en equivalentes solo porque compartan tokens. Las razones se guardan en `MatchSuggestion` para que la revisión no dependa de una cifra opaca.

Una consolidación siempre deja `ProductLink`. El vínculo conserva producto original, canónico, confianza, origen y confirmador. Revertir un vínculo elimina la relación sin borrar la fila original del proveedor.

## Fronteras operativas

- El LLM se configura por `LLM_API_KEY`, `LLM_API_URL` y `LLM_MODEL`; sin clave, el agente informa que no está configurado.
- `AGENT_MEMORY_MAX_MESSAGES` limita el historial reciente enviado al LLM (30); `AGENT_SUMMARY_THRESHOLD` inicia el resumen de la conversación (60).
- No se inventan datos: los estados vacíos del frontend reflejan tablas vacías.
- El frontend consume exclusivamente `/api/v1` y no contiene métricas de demostración.
