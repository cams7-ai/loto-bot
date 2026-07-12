from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import AppContainer, get_container
from api.mappers import ApiExceptionMapper, ApiResponseMapper
from api.schemas import (
    ErrorResponse,
    SessionControlResponse,
    SessionStatusResponse,
    error_response_examples,
)
from domain import (
    AutomationError,
    ErrorCode,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
CONTAINER_DEPENDENCY = Depends(get_container)


def error_response(description: str, *codes: ErrorCode) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json; charset=utf-8": {
                "examples": error_response_examples(*codes),
            }
        },
    }


ERROR_RESPONSE_BY_STATUS = {
    400: error_response("Requisição inválida", ErrorCode.BAD_REQUEST, ErrorCode.INVALID_CPF_ERROR_CODE),
    409: error_response(
        "Sessão de navegador já está aberta ou fechada",
        ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE,
        ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE,
    ),
    500: error_response(
        "Erro interno ou de automação",
        ErrorCode.AUTOMATION_ERROR_CODE,
        ErrorCode.INTERNAL_SERVER_ERROR,
    ),
    502: error_response(
        "Falha de comunicação ou redirecionamento no portal externo", ErrorCode.PAGE_REDIRECTION_ERROR_CODE
    ),
    503: error_response("Serviço externo indisponível", ErrorCode.EXTERNAL_SERVICE_ERROR_CODE),
}

START_ERROR_RESPONSES = {
    status_code: ERROR_RESPONSE_BY_STATUS[status_code] for status_code in (400, 409, 500, 502, 503)
}

STOP_ERROR_RESPONSES = {status_code: ERROR_RESPONSE_BY_STATUS[status_code] for status_code in (409, 500)}

STATUS_ERROR_RESPONSES = {
    500: ERROR_RESPONSE_BY_STATUS[500],
}


@router.get("/start", response_model=SessionControlResponse, responses=START_ERROR_RESPONSES)
async def start_session(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionControlResponse | None:
    try:
        result = container.session_control.start()
        return ApiResponseMapper.session_response(result, "Sessão de navegador iniciada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/stop", response_model=SessionControlResponse, responses=STOP_ERROR_RESPONSES)
async def stop_session(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionControlResponse | None:
    try:
        result = container.session_control.stop()
        return ApiResponseMapper.session_response(result, "Sessão de navegador encerrada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/status", response_model=SessionStatusResponse, responses=STATUS_ERROR_RESPONSES)
async def session_status(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionStatusResponse:
    result = container.session_control.status()
    return ApiResponseMapper.session_response(result, "Status da sessão obtido com sucesso")
