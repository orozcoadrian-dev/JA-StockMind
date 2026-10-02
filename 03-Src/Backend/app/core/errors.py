import logging
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException
from starlette.requests import Request


HTTP_MESSAGES = {
    400: "La solicitud no es válida.",
    405: "El método HTTP no está permitido para este recurso.",
    404: "No se encontró el recurso solicitado.",
    409: "La solicitud entra en conflicto con el estado actual.",
    413: "El archivo supera el tamaño máximo permitido.",
    422: "La solicitud no cumple el formato requerido.",
    429: "Se excedió el límite de solicitudes. Inténtalo más tarde.",
    500: "Ocurrió un error interno.",
    503: "El servicio no está disponible temporalmente.",
}
logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app) -> None:
    from Backend.Services.api_v1 import APIServiceError

    @app.exception_handler(APIServiceError)
    async def service_error_handler(request: Request, exc: APIServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(f"HTTP_{exc.status_code}", exc.message, exc.details),
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error_payload("HTTP_429", HTTP_MESSAGES[429]),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = [
            {
                "field": ".".join(str(part) for part in issue.get("loc", ()) if part != "body"),
                "message": "El valor no cumple el formato o los límites permitidos.",
                "type": issue.get("type", "validation_error"),
            }
            for issue in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload("VALIDATION_ERROR", HTTP_MESSAGES[422], {"fields": fields}),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        default_messages = {"Not Found", "Method Not Allowed", "Internal Server Error"}
        message = exc.detail if isinstance(exc.detail, str) and exc.detail not in default_messages else HTTP_MESSAGES.get(exc.status_code, HTTP_MESSAGES[500])
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_payload(f"HTTP_{exc.status_code}", message, exc.detail if isinstance(exc.detail, dict) else {}),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Error no controlado al procesar %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_ERROR", HTTP_MESSAGES[500]),
        )