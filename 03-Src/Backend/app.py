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
]


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "imperio-motos-agent"}


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
