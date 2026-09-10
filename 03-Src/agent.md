# Agent.md

## Propósito
Este proyecto es un PoC funcional para un entorno agéntico de gestión de inventarios en Imperio Motos SAS. El objetivo principal es detectar SKUs duplicados o ambiguos entre proveedores y recomendar acciones de fusión o revisión humana.

## Arquitectura
- Backend en Python con FastAPI
- Agente semántico simulado en `backend/agent.py`
- Frontend estático en `Frontend/` usando HTML, CSS y JavaScript
- API principal: `/api/compare-skus`
- Datos de ejemplo: `/api/ambiguous-skus`

## Lógica del agente
El agente recibe dos cadenas de texto, normaliza el contenido y calcula:
1. Solapamiento de términos clave
2. Similitud textual mediante `difflib`
3. Traducción semántica usando un diccionario de sinónimos del dominio

Con esos elementos, devuelve:
- `confidence`: porcentaje de similitud
- `recommendation`: `Fusionar` o `Revisar`
- `evidence`: métricas internas para interpretación humana

## Cómo ejecutar
1. Crear entorno virtual
2. Instalar dependencias
3. Ejecutar el backend con `uvicorn Backend.app:app --reload --host 0.0.0.0 --port 8000`
4. Abrir la landing page y la pantalla de inventario

## Buenas prácticas aplicadas
- Separación de responsabilidades entre backend y frontend
- CORS habilitado para consumo local del frontend
- Diseño responsive con CSS Grid/Flexbox
- Comentarios claros dentro del código para facilitar la explicación académica
