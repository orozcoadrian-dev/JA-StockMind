# Imperio Motos SAS - AI Inventory Agent PoC

Este repositorio contiene un PoC funcional para un sistema agéntico de gestión de inventarios con detección de SKUs duplicados entre proveedores.

## Objetivo
Desarrollar una prueba de concepto para un parcial de 6to semestre, con enfoque en:
- Backend en Python
- Agente IA semántico
- Frontend moderno y responsivo
- Flujo Human-in-the-Loop para revisión de inventarios ambiguos

## Estructura del proyecto

```text
03-Src/
├── Backend/
│   ├── __init__.py
│   ├── agent.py
│   ├── app.py
│   ├── requirements.txt
│   └── ...
├── Frontend/
│   ├── index.html
│   ├── inventario.html
│   ├── styles.css
│   └── script.js
├── README.md
├── agent.md
└── .gitignore
```

## Requisitos previos
- Python 3.10+
- Navegador moderno
- Git

## Instalación

```bash
cd 03-Src
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r Backend/requirements.txt
```

## Ejecución del backend

```bash
cd 03-Src
uvicorn Backend.app:app --reload --host 0.0.0.0 --port 8000
```

## Uso del frontend

1. Abre `Frontend/index.html` en tu navegador.
2. Navega a la pantalla de inventario haciendo clic en el botón correspondiente.
3. En la vista de inventario, presiona `Ejecutar Agente` para comparar SKUs.

## API principal

### GET `/health`
Verifica que el servicio esté activo.

### GET `/api/ambiguous-skus`
Devuelve una lista de inventarios ambiguos de ejemplo.

### POST `/api/compare-skus`
Recibe:

```json
{
  "sku_a": "Manilar rojo",
  "sku_b": "Grip rojo"
}
```

Respuesta esperada:

```json
{
  "status": "success",
  "analysis": {
    "similarity": 92.34,
    "confidence": 92.34,
    "recommendation": "Fusionar",
    "message": "Se recomienda fusionar los SKUs por alta similitud semántica."
  }
}
```

## Ejemplo de primer commit

```bash
git add .
git commit -m "feat: initialize imperio motos inventory agent poc"
```

## Notes académicos
Este PoC está orientado a demostrar una arquitectura limpia, un agente semántico simplificado y una interfaz útil para revisión humana. El proyecto puede extenderse con:
- Base de datos
- Autenticación
- Validaciones más avanzadas de similitud
- Integración con modelos de embeddings o NLP

## Autoría
Proyecto de Adrián Orozco y Jaber Vargas
