from __future__ import annotations

from fastapi import status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException

from api.exception_handlers import (
    api_error_handler,
    http_exception_handler,
    request_validation_error_handler,
    unhandled_exception_handler,
)
from api.exceptions import ApiError


class Model(BaseModel):
    name: str


def make_validation_error() -> RequestValidationError:
    try:
        Model.model_validate({"name": 1})
    except ValidationError as exc:
        return RequestValidationError(exc.errors())
    raise AssertionError("Erro de validação esperado")


async def test_api_error_handler(anyio_backend):
    response = await api_error_handler(None, ApiError(status_code=400, code="CODIGO", message="Mensagem", fields=["name"]))
    assert response.status_code == 400
    assert response.body.decode("utf-8")


async def test_request_validation_error_handler(anyio_backend):
    response = await request_validation_error_handler(None, make_validation_error())
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "REQUISICAO_INVALIDA" in response.body.decode("utf-8")


async def test_http_exception_handler(anyio_backend):
    not_found = await http_exception_handler(None, HTTPException(status_code=404))
    method = await http_exception_handler(None, HTTPException(status_code=405))
    bad = await http_exception_handler(None, HTTPException(status_code=418, detail="curto"))

    assert "ROTA_NAO_ENCONTRADA" in not_found.body.decode("utf-8")
    assert "METODO_NAO_PERMITIDO" in method.body.decode("utf-8")
    assert "curto" in bad.body.decode("utf-8")


async def test_unhandled_exception_handler(anyio_backend):
    response = await unhandled_exception_handler(None, RuntimeError("falha"))
    assert response.status_code == 500
    assert "ERRO_INTERNO" in response.body.decode("utf-8")
