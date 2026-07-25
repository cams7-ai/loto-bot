"""Tratamento centralizado de erros HTTP."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.exceptions import ApiError
from api.responses import Utf8JSONResponse
from domain import ErrorCode
from shared import sao_paulo_timezone

logger = logging.getLogger(__name__)


async def api_error_handler(_: Request, exc: ApiError) -> Utf8JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def request_validation_error_handler(_: Request, __: RequestValidationError) -> Utf8JSONResponse:
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=ErrorCode.BAD_REQUEST,
        message="Corpo da requisição inválido.",
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> Utf8JSONResponse:
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return _error_response(status_code=404, code=ErrorCode.NOT_FOUND, message="Rota não encontrada.")
    if exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        return _error_response(
            status_code=405, code=ErrorCode.METHOD_NOT_ALLOWED, message="Método HTTP não permitido para esta rota."
        )
    detail = exc.detail if isinstance(exc.detail, str) else "Erro na requisição."
    return _error_response(status_code=exc.status_code, code=ErrorCode.BAD_REQUEST, message=detail)


async def unhandled_exception_handler(_: Request, exc: Exception) -> Utf8JSONResponse:
    logger.exception("Erro inesperado fora do fluxo principal da API")
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        message="Erro inesperado ao processar a requisição.",
    )


def _error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> Utf8JSONResponse:
    error: dict[str, Any] = {
        "status_code": status_code,
        "code": code.value,
    }
    if details is not None:
        error["timestamp"] = datetime.now(sao_paulo_timezone()).replace(microsecond=0).isoformat()
    if message is not None:
        error["message"] = message
    if details is not None:
        error["details"] = details
    return Utf8JSONResponse(status_code=status_code, content={"error": error})
