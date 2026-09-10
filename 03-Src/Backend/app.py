from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from Backend.agent import SemanticAgent

app = FastAPI(
    title="Imperio Motos SAS - Inventory Agent PoC",
    description="PoC funcional de agente IA para detectar SKUs duplicados y sugerir fusión.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = SemanticAgent()


class CompareRequest(BaseModel):
    sku_a: str
    sku_b: str


AMBIGUOUS_SKUS = [
    {
        "id": 1,
        "provider_a": "Proveedor Alpha",
        "sku_a": "Manilar rojo",
        "provider_b": "Proveedor Beta",
        "sku_b": "Grip rojo",
        "reason": "Candidatos con nomenclatura similar pero proveedores distintos.",
    },
    {
        "id": 2,
        "provider_a": "Proveedor Delta",
        "sku_a": "Asiento negro para moto",
        "provider_b": "Proveedor Gamma",
        "sku_b": "Sillin negro moto",
        "reason": "Sinónimos del dominio: asiento/sillin.",
    },
    {
        "id": 3,
        "provider_a": "Proveedor Omega",
        "sku_a": "Faro delantero LED",
        "provider_b": "Proveedor Zeta",
        "sku_b": "Faro LED delantero",
        "reason": "Misma referencia con orden distinto de palabras.",
    },
    {
        "id": 4,
        "provider_a": "Proveedor Epsilon",
        "sku_a": "Filtro de aceite 1.5L",
        "provider_b": "Proveedor Theta",
        "sku_b": "Filtro aceite moto 1.5",
        "reason": "Descripción equivalente con diferencia en unidades y formato.",
    },
    {
        "id": 5,
        "provider_a": "Proveedor Lambda",
        "sku_a": "Mango negro para moto",
        "provider_b": "Proveedor Mu",
        "sku_b": "Manillar negro",
        "reason": "Se refiere al mismo componente con nombres alternativos.",
    },
]

PRODUCTS = [
    {
        "id": 1,
        "name": "Grip rojo para moto",
        "category": "Manillar",
        "stock": 46,
        "stock_limit": 60,
        "supplier": "Proveedor Alpha",
        "price": 185000,
        "status": "Activo",
        "trend": 12,
        "location": "Bodega Norte",
    },
    {
        "id": 2,
        "name": "Asiento negro para moto",
        "category": "Accesorios",
        "stock": 18,
        "stock_limit": 30,
        "supplier": "Proveedor Delta",
        "price": 420000,
        "status": "Revisar",
        "trend": 7,
        "location": "Bodega Sur",
    },
    {
        "id": 3,
        "name": "Faro delantero LED",
        "category": "Iluminación",
        "stock": 33,
        "stock_limit": 40,
        "supplier": "Proveedor Omega",
        "price": 260000,
        "status": "Activo",
        "trend": 18,
        "location": "Bodega Central",
    },
    {
        "id": 4,
        "name": "Filtro de aceite 1.5L",
        "category": "Mantenimiento",
        "stock": 9,
        "stock_limit": 25,
        "supplier": "Proveedor Epsilon",
        "price": 59000,
        "status": "Alerta",
        "trend": -4,
        "location": "Bodega Este",
    },
    {
        "id": 5,
        "name": "Amortiguador trasero",
        "category": "Suspensión",
        "stock": 21,
        "stock_limit": 22,
        "supplier": "Proveedor Kappa",
        "price": 310000,
        "status": "Activo",
        "trend": 10,
        "location": "Bodega Central",
    },
]

DASHBOARD_SUMMARY = {
    "inventoryHealth": 96,
    "stockAlerts": 8,
    "pendingReview": 5,
    "weeklySales": "$128.4M",
    "reservedStock": 62,
    "topCategory": "Manillares y grips",
}

ALERTS = [
    {"id": 1, "severity": "Alta", "text": "Se detectaron 3 posibles duplicados entre proveedores en la categoría de grips.", "time": "Hace 12 min"},
    {"id": 2, "severity": "Media", "text": "Inventario bajo en filtros de aceite: solo quedan 9 unidades disponibles.", "time": "Hace 35 min"},
    {"id": 3, "severity": "Baja", "text": "Se generó una nueva revisión de ejemplo para el producto de asiento negro.", "time": "Hace 1 hora"},
]

ACTIVITY = [
    {"id": 1, "title": "Se ejecutó el agente sobre 5 registros", "meta": "10:25 AM"},
    {"id": 2, "title": "Se validó la fusión de Grip rojo", "meta": "09:42 AM"},
    {"id": 3, "title": "Se actualizó el stock del producto Faro LED", "meta": "08:15 AM"},
]

REPORTS = {
    "revenueForecast": "$240.6M",
    "fulfilledOrders": 84,
    "potentialSavings": "$31.2M",
    "categoryDistribution": [
        {"label": "Manillares", "value": 34, "color": "#32d76b"},
        {"label": "Iluminación", "value": 22, "color": "#8bf5b1"},
        {"label": "Suspensión", "value": 18, "color": "#ffbf69"},
        {"label": "Mantenimiento", "value": 14, "color": "#ff6b6b"},
        {"label": "Accesorios", "value": 12, "color": "#5ecbff"},
    ],
    "recommendations": [
        "Fusionar Grip rojo y Manillar rojo, la similitud es superior al 92%.",
        "Revisar el asiento negro antes de consolidar porque hay una variación de color.",
        "Solicitar un reporte adicional del filtro de aceite para prevenir falta de stock.",
    ],
    "forecast": [
        {"label": "Semana 1", "value": 72},
        {"label": "Semana 2", "value": 79},
        {"label": "Semana 3", "value": 84},
        {"label": "Semana 4", "value": 89},
    ],
}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "imperio-motos-agent"}


@app.get("/api/dashboard")
def get_dashboard():
    return {
        "summary": DASHBOARD_SUMMARY,
        "alerts": ALERTS,
        "activity": ACTIVITY,
        "products": PRODUCTS,
    }


@app.get("/api/products")
def get_products():
    return {"items": PRODUCTS}


@app.get("/api/reports")
def get_reports():
    return {"data": REPORTS}


@app.get("/api/ambiguous-skus")
def get_ambiguous_skus():
    """Devuelve una lista inicial de productos ambiguos simulados."""
    return {"items": AMBIGUOUS_SKUS}


@app.post("/api/compare-skus")
def compare_skus(payload: CompareRequest):
    """Compara dos SKUs usando el agente semántico simulado."""
    try:
        analysis = agent.compare_skus(payload.sku_a, payload.sku_b)
        return {
            "status": "success",
            "analysis": analysis,
        }
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Backend.app:app", host="0.0.0.0", port=8000, reload=True)
