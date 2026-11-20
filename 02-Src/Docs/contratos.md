# Contratos JSON del sistema MotoStock

Este documento describe los contratos de entrada y salida que usa el backend. La idea es mantener un contrato claro entre la API, el motor de equivalencias y el agente.

---

## 1. Supplier

Representa un proveedor que entrega listas de precios.

### Ejemplo de entrada

```json
{
  "name": "Inversiones Guerrero",
  "nit": "900123456-7",
  "contact": "Carlos Ruiz",
  "active": true
}
```

### Ejemplo de salida

```json
{
  "id": 1,
  "name": "Inversiones Guerrero",
  "nit": "900123456-7",
  "contact": "Carlos Ruiz",
  "active": true,
  "created_at": "2026-09-14T12:00:00Z"
}
```

**Notas**
- `name` es único para evitar duplicar proveedores.
- `active` indica si el proveedor sigue en operación.

---

## 2. Product

Es el registro tal como llega del Excel del proveedor, sin consolidar ni modificar la semántica del producto original.

### Ejemplo de entrada

```json
{
  "supplier_id": 1,
  "provider_code": "IG-4471",
  "raw_name": "GRIP ROJO DEPORTIVO",
  "normalized_name": "grip rojo deportivo",
  "category": "manillar",
  "unit_price": 185000,
  "currency": "COP",
  "unit_of_measure": "unidad",
  "pack_quantity": 1,
  "price_list_date": "2026-09-01",
  "row_hash": "abd12f90c3d5f1e4e6023a81db9bd9ab"
}
```

### Ejemplo de salida

```json
{
  "id": 10,
  "supplier_id": 1,
  "provider_code": "IG-4471",
  "raw_name": "GRIP ROJO DEPORTIVO",
  "normalized_name": "grip rojo deportivo",
  "category": "manillar",
  "unit_price": 185000,
  "currency": "COP",
  "unit_of_measure": "unidad",
  "pack_quantity": 1,
  "price_list_date": "2026-09-01",
  "row_hash": "abd12f90c3d5f1e4e6023a81db9bd9ab",
  "created_at": "2026-09-14T12:00:00Z"
}
```

**Notas**
- `raw_name` conserva exactamente el texto del Excel.
- `normalized_name` se usa para búsquedas y comparaciones.
- `row_hash` evita duplicados dentro del mismo archivo y permite idempotencia.

---

## 3. CanonicalProduct

Es el producto real y unificado del catálogo del almacén, después de consolidar múltiples referencias.

### Ejemplo de entrada

```json
{
  "name": "Grip rojo deportivo",
  "category": "manillar",
  "attributes": {
    "color": "rojo",
    "type": "grip",
    "measure": "22mm",
    "compatible_brand": "Kawasaki"
  },
  "stock_in_bodega": 45,
  "minimum_stock": 10
}
```

### Ejemplo de salida

```json
{
  "id": 3,
  "name": "Grip rojo deportivo",
  "category": "manillar",
  "attributes": {
    "color": "rojo",
    "type": "grip",
    "measure": "22mm",
    "compatible_brand": "Kawasaki"
  },
  "stock_in_bodega": 45,
  "minimum_stock": 10,
  "created_at": "2026-09-14T12:00:00Z"
}
```

**Notas**
- `attributes` debe ser un JSON libre, pero se recomienda mantener un esquema semántico estable para color, medida, marca compatible y tipo.

---

## 4. ProductLink

Une un producto proveedor con un producto canónico, con nivel de confianza y origen del vínculo.

### Ejemplo de entrada

```json
{
  "product_id": 10,
  "canonical_product_id": 3,
  "confidence": 0.96,
  "origin": "rule",
  "confirmed_by": "usuario@almacen"
}
```

### Ejemplo de salida

```json
{
  "id": 50,
  "product_id": 10,
  "canonical_product_id": 3,
  "confidence": 0.96,
  "origin": "rule",
  "confirmed_by": "usuario@almacen",
  "created_at": "2026-09-14T12:00:00Z"
}
```

**Notas**
- `origin` puede ser: `rule`, `agent_suggestion`, `manual_confirmation`.
- `confidence` va de `0` a `1`.

---

## 5. EquivalenceRule

Representa la regla que dicta el usuario en lenguaje natural, convertida a una estructura ejecutable.

### Ejemplo de equivalencia entre proveedores

```json
{
  "original_text": "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo",
  "structured_condition": {
    "type": "supplier_equivalence",
    "match": {
      "keywords": ["grip", "rojo"],
      "attributes": {"color": "rojo", "type": "grip"}
    },
    "suppliers": ["Inversiones Guerrero", "Malusa"],
    "action": "merge_to_canonical",
    "confidence": 1.0
  },
  "supplier_names": ["Inversiones Guerrero", "Malusa"],
  "active": true
}
```

### Ejemplo de exclusión

```json
{
  "original_text": "un grip rojo de 22mm no puede fusionarse con uno de 28mm aunque se parezcan",
  "structured_condition": {
    "type": "exclusion",
    "match": {
      "keywords": ["grip", "rojo"],
      "attributes": {"measure": "22mm"}
    },
    "suppliers": ["Guerrero", "Malusa"],
    "action": "block_merge",
    "confidence": 0.99
  },
  "supplier_names": ["Guerrero", "Malusa"],
  "active": true
}
```

### Ejemplo de preferencia de compra

```json
{
  "original_text": "para frenos, prefiere Distrimotos",
  "structured_condition": {
    "type": "purchase_preference",
    "match": {
      "category": "frenos"
    },
    "suppliers": ["Distrimotos"],
    "action": "prefer_supplier",
    "confidence": 0.95
  },
  "supplier_names": ["Distrimotos"],
  "active": true
}
```

**Notas**
- `type` puede ser: `supplier_equivalence`, `exclusion` o `purchase_preference`.
- `action` puede ser: `merge_to_canonical`, `block_merge` o `prefer_supplier`.
- `confidence` permite graduar la fuerza con la que la regla debe aplicarse.

---

## 6. AgentAction

El agente registra cada acción ejecutada con la intención de auditar decisiones y mantener trazabilidad.

### Ejemplo de entrada

```json
{
  "tool_name": "suggest_matches",
  "input_payload": {
    "product_id": 10,
    "category": "manillar"
  },
  "result": {
    "status": "success",
    "matches_found": 3
  },
  "required_confirmation": true,
  "approved": true
}
```

### Ejemplo de salida

```json
{
  "id": 88,
  "tool_name": "suggest_matches",
  "input_payload": {
    "product_id": 10,
    "category": "manillar"
  },
  "result": {
    "status": "success",
    "matches_found": 3
  },
  "required_confirmation": true,
  "approved": true,
  "timestamp": "2026-09-14T12:10:30Z"
}
```

**Notas**
- Sirve para auditoría del entorno agéntico.
- Cada acción puede requerir confirmación antes de producir un cambio destructivo.

---

## 7. Reglas de diseño

- Los índices prioritarios son `normalized_name` y `supplier_id`.
- El JSON estructurado debe ser serializable y fácil de consultar con SQLAlchemy JSON.
- Cada regla debe quedar con su texto original y su versión ejecutable.
- El sistema debe poder distinguir equivalencias, exclusiones y preferencias de compra sin ambigüedad.

---

## 8. ChatSession y ChatMessage

`ChatSession.external_id` es UUID4. `ChatMessage` conserva el historial con secuencia consecutiva; los resúmenes son mensajes `system` con metadatos, y no reemplazan ni eliminan los mensajes originales de la base.

### Enviar chat

`POST /api/v1/agent/chat`

```json
{
  "message": "Compara los precios de frenos",
  "session_id": "d2719b7e-7d7a-48a6-a012-31fae2d4d000"
}
```

- `message`: requerido, entre 1 y 8000 caracteres.
- `session_id`: opcional, solo UUID4; si se omite se crea una sesión.
- Un mensaje demasiado largo o un ID con formato inválido devuelve 422.

### Sesiones y mensajes

- `GET /api/v1/agent/sessions?status=active&limit=20&offset=0`: lista paginada.
- `POST /api/v1/agent/sessions`: crea sesión.
- `GET /api/v1/agent/sessions/{uuid4}`: consulta metadatos.
- `GET /api/v1/agent/sessions/{uuid4}/messages?limit=50&include_tools=false`: lee historial ordenado por `seq`.
- `PATCH /api/v1/agent/sessions/{uuid4}`: renombra o archiva/reactiva.
- `GET /api/v1/agent/sessions/{uuid4}/export`: exporta mensajes y datos de sesión.

Las respuestas exitosas usan `{ "data": ..., "meta": ... }`; los errores usan `{ "error": { "code", "message", "details" } }`.

## 9. AgentMemoryFact

Cada fact persistido contiene `id`, `key`, `value`, `source_session_id`, `source_message_id` nullable, `status` (`active|disabled`), `created_at` y `updated_at`. Guardar facts requiere la confirmación de `remember_fact`; `list_memory_facts` solo devuelve facts activos. Los facts deshabilitados se conservan.

- `GET /api/v1/agent/memory/facts?status=active&limit=20&offset=0`: lista facts; `status` también acepta `disabled` y `all`.
- `PATCH /api/v1/agent/memory/facts/{id}` con `{"status":"disabled"}`: deshabilita sin borrar.
- `AGENT_MEMORY_MAX_MESSAGES` (30 por defecto) limita el contexto reciente.
- `AGENT_SUMMARY_THRESHOLD` (60 por defecto) dispara resúmenes LLM guardados como mensajes `system`; los mensajes fuente permanecen disponibles en el historial.

**Seguridad:** UUID4 reduce la posibilidad de adivinar IDs, pero no sustituye autenticación. Las rutas de sesión, acciones y facts no tienen autorización por usuario y el listado de sesiones es global; no exponerlas a clientes no confiables hasta implementar propiedad y aislamiento.
