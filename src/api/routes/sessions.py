from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import AppContainer, get_container
from api.mappers import ApiExceptionMapper, ApiResponseMapper
from api.responses import error_response, success_response
from api.schemas import (
    SessionControlResponse,
    SessionStatusResponse,
)
from domain import (
    AutomationError,
    AutomationStatus,
    ErrorCode,
    Operation,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
CONTAINER_DEPENDENCY = Depends(get_container)

ERROR_RESPONSE_BY_STATUS = {
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

START_ERROR_RESPONSES = {status_code: ERROR_RESPONSE_BY_STATUS[status_code] for status_code in (409, 500, 502, 503)}

STOP_ERROR_RESPONSES = {status_code: ERROR_RESPONSE_BY_STATUS[status_code] for status_code in (409, 500)}

STATUS_ERROR_RESPONSES = {
    500: ERROR_RESPONSE_BY_STATUS[500],
}

START_RESPONSES = {
    200: success_response(
        "Sessão de navegador iniciada com sucesso",
        {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "status": AutomationStatus.OPEN.value,
            "executed_operation": Operation.START_SESSION.value,
            "message": "Sessão de navegador iniciada com sucesso",
            "is_open": True,
        },
    ),
    **START_ERROR_RESPONSES,
}

STOP_RESPONSES = {
    200: success_response(
        "Sessão de navegador encerrada com sucesso",
        {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "status": AutomationStatus.CLOSED.value,
            "executed_operation": Operation.END_SESSION.value,
            "message": "Sessão de navegador encerrada com sucesso",
            "is_open": False,
        },
    ),
    **STOP_ERROR_RESPONSES,
}

STATUS_RESPONSES = {
    200: success_response(
        "Status da sessão obtido com sucesso",
        {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "status": AutomationStatus.OPEN.value,
            "executed_operation": Operation.START_SESSION.value,
            "is_open": True,
        },
    ),
    **STATUS_ERROR_RESPONSES,
}


@router.get("/start", response_model=SessionControlResponse, responses=START_RESPONSES)
async def start_session(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionControlResponse | None:
    try:
        result = container.session_control.start()
        return ApiResponseMapper.session_response(result, "Sessão de navegador iniciada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/stop", response_model=SessionControlResponse, responses=STOP_RESPONSES)
async def stop_session(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionControlResponse | None:
    try:
        result = container.session_control.stop()
        return ApiResponseMapper.session_response(result, "Sessão de navegador encerrada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/status", response_model=SessionStatusResponse, responses=STATUS_RESPONSES)
async def session_status(container: AppContainer = CONTAINER_DEPENDENCY) -> SessionControlResponse:
    result = container.session_control.status()
    return ApiResponseMapper.session_response(result, "Status da sessão obtido com sucesso")
