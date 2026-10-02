from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.errors import register_exception_handlers
from .core.logging import configure_logging
from .core.rate_limit import limiter
from .core.upload_limit import UploadSizeLimitMiddleware
from .routers.agent import router as agent_router
from .routers.canonical_products import router as canonical_products_router
from .routers.health import router as health_router
from .routers.imports import router as imports_router
from .routers.matches import router as matches_router
from .routers.products import router as products_router
from .routers.reports import router as reports_router
from .routers.rules import router as rules_router
from .routers.suppliers import router as suppliers_router


settings = get_settings()
configure_logging()

app = FastAPI(
    title="JA-StockMind",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(UploadSizeLimitMiddleware, max_bytes=settings.MAX_UPLOAD_MB * 1024 * 1024)
app.state.limiter = limiter
app.include_router(health_router, prefix="/api/v1")
app.include_router(suppliers_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(canonical_products_router, prefix="/api/v1")
app.include_router(matches_router, prefix="/api/v1")
app.include_router(rules_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
register_exception_handlers(app)