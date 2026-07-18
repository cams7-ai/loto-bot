"""API REST do LotoBot."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.exception_handlers import (
    api_error_handler,
    http_exception_handler,
    request_validation_error_handler,
    unhandled_exception_handler,
)
from api.exceptions import ApiError
from api.openapi import OPENAPI_TAGS
from api.responses import Utf8JSONResponse
from api.routes import bets_router, health_router, placed_bets_router, sessions_router

app = FastAPI(
    title="LotoBot API",
    description="API REST para controlar uma automação do portal Loterias Online CAIXA.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    default_response_class=Utf8JSONResponse,
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(bets_router)
app.include_router(placed_bets_router)


def custom_openapi() -> dict[str, object]:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = app.original_openapi()
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses")
            if isinstance(responses, dict):
                responses.pop("422", None)

    schemas = openapi_schema.get("components", {}).get("schemas", {})
    if isinstance(schemas, dict):
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.original_openapi = app.openapi
app.openapi = custom_openapi
