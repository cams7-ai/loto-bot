from __future__ import annotations

from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, ConfigDict

from application.services.portal_bet_filter_catalog import ALL
from domain import (
    ErrorCode,
    ErrorMessage,
    LotteryModality,
)


def error_example(
    status_code: HTTPStatus,
    code: ErrorCode,
    message: str,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "status_code": status_code.value,
        "code": code.value,
        "message": message,
    }
    return {"error": error}


ERROR_EXAMPLES = {
    ErrorCode.BAD_REQUEST: {
        "error": {
            "timestamp": "2026-06-16T10:00:00-03:00",
            "status_code": HTTPStatus.BAD_REQUEST.value,
            "code": ErrorCode.BAD_REQUEST.value,
            "message": "Parâmetros inválidos",
            "details": [
                {
                    "field": "lottery_modality",
                    "rejected_value": "abc",
                    "allowed_values": [ALL, *LotteryModality.__members__],
                    "message": "Valor inválido.",
                }
            ],
        }
    },
    ErrorCode.NOT_FOUND: error_example(
        HTTPStatus.NOT_FOUND,
        ErrorCode.NOT_FOUND,
        "Aposta não encontrada.",
    ),
    ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE,
        ErrorMessage.BROWSER_SESSION_OPEN,
    ),
    ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE,
        ErrorMessage.BROWSER_SESSION_CLOSED,
    ),
    ErrorCode.INVALID_CPF_ERROR_CODE: error_example(
        HTTPStatus.BAD_REQUEST,
        ErrorCode.INVALID_CPF_ERROR_CODE,
        ErrorMessage.INVALID_CPF,
    ),
    ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE: error_example(
        HTTPStatus.FORBIDDEN,
        ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE,
        ErrorMessage.PAYMENT_CONFIRMATION_DISABLED,
    ),
    ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE,
        ErrorMessage.INDIVIDUAL_BET_REGISTRATION_CLOSED,
    ),
    ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE,
        ErrorMessage.BET_TEMPORARILY_DISABLED.format(modality="mega-sena"),
    ),
    ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE: error_example(
        HTTPStatus.TOO_MANY_REQUESTS,
        ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE,
        ErrorMessage.DAILY_PURCHASE_LIMIT,
    ),
    ErrorCode.BETS_NOT_AVAILABLE_FOR_CAPTURE_ERROR_CODE: error_example(
        HTTPStatus.CONFLICT,
        ErrorCode.BETS_NOT_AVAILABLE_FOR_CAPTURE_ERROR_CODE,
        ErrorMessage.BETS_NOT_AVAILABLE_FOR_CAPTURE,
    ),
    ErrorCode.PAGE_REDIRECTION_ERROR_CODE: error_example(
        HTTPStatus.BAD_GATEWAY,
        ErrorCode.PAGE_REDIRECTION_ERROR_CODE,
        ErrorMessage.PAGE_REDIRECTION_ERROR.format(path="/pagamento"),
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
    timestamp: str | None = None
    status_code: int
    code: str
    message: str | None = None
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": list(ERROR_EXAMPLES.values())})

    error: ErrorDetail
