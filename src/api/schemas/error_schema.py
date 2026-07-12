from __future__ import annotations

from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, ConfigDict

from domain import (
    BET_TEMPORARILY_DISABLED,
    BROWSER_SESSION_CLOSED,
    BROWSER_SESSION_OPEN,
    DAILY_PURCHASE_LIMIT,
    INDIVIDUAL_BET_REGISTRATION_CLOSED,
    INVALID_CPF,
    PAGE_REDIRECTION_ERROR,
    PAYMENT_CONFIRMATION_DISABLED,
    ErrorCode,
)


def error_example(
    status_code: HTTPStatus,
    code: ErrorCode,
    message: str,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "status_code": status_code.value,
        "code": code.value,
        "message": message,
    }
    if fields is not None:
        error["fields"] = fields
    return {"error": error}


ERROR_EXAMPLES = {
    ErrorCode.BAD_REQUEST: error_example(
        HTTPStatus.BAD_REQUEST,
        ErrorCode.BAD_REQUEST,
        "Corpo da requisição inválido.",
        ["cpf"],
    ),
    ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE,
        BROWSER_SESSION_OPEN,
    ),
    ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE,
        BROWSER_SESSION_CLOSED,
    ),
    ErrorCode.INVALID_CPF_ERROR_CODE: error_example(
        HTTPStatus.BAD_REQUEST,
        ErrorCode.INVALID_CPF_ERROR_CODE,
        INVALID_CPF,
    ),
    ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE: error_example(
        HTTPStatus.FORBIDDEN,
        ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE,
        PAYMENT_CONFIRMATION_DISABLED,
    ),
    ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE,
        INDIVIDUAL_BET_REGISTRATION_CLOSED,
    ),
    ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE,
        BET_TEMPORARILY_DISABLED.format(modality="mega-sena"),
    ),
    ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE: error_example(
        HTTPStatus.TOO_MANY_REQUESTS,
        ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE,
        DAILY_PURCHASE_LIMIT,
    ),
    ErrorCode.PAGE_REDIRECTION_ERROR_CODE: error_example(
        HTTPStatus.BAD_GATEWAY,
        ErrorCode.PAGE_REDIRECTION_ERROR_CODE,
        PAGE_REDIRECTION_ERROR.format(path="/pagamento"),
    ),
    ErrorCode.AUTOMATION_ERROR_CODE: error_example(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorCode.AUTOMATION_ERROR_CODE,
        "A operação não pôde ser concluída neste momento",
    ),
    ErrorCode.INTERNAL_SERVER_ERROR: error_example(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_SERVER_ERROR,
        "Erro inesperado ao processar a requisição.",
    ),
    ErrorCode.EXTERNAL_SERVICE_ERROR_CODE: error_example(
        HTTPStatus.SERVICE_UNAVAILABLE,
        ErrorCode.EXTERNAL_SERVICE_ERROR_CODE,
        "Serviço externo indisponível",
    ),
}


def error_response_examples(*codes: ErrorCode) -> dict[str, dict[str, Any]]:
    return {
        code.value: {
            "summary": code.value,
            "value": ERROR_EXAMPLES[code],
        }
        for code in codes
    }


class ErrorDetail(BaseModel):
    status_code: int
    code: str
    message: str
    fields: list[str] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": list(ERROR_EXAMPLES.values())})

    error: ErrorDetail
