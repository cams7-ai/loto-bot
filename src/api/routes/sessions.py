from __future__ import annotations

from fastapi import APIRouter, Depends, status

from api.dependencies import AppContainer, get_container
from api.exceptions import ApiError
from api.schemas import ErrorResponse, SessionControlResponse, SessionStatusResponse
from domain import AutomationError, BrowserSessionClosedError, BrowserSessionOpenError, ExternalServiceError

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Erro de requisição"},
    500: {"model": ErrorResponse, "description": "Erro interno"},
}


@router.get("/start", response_model=SessionControlResponse, responses=ERROR_RESPONSES)
async def start_session(container: AppContainer = Depends(get_container)) -> SessionControlResponse:
    try:
        result = container.session_control.start()
        return _control_response(result, "Sessão de navegador iniciada com sucesso.")
    except AutomationError as exc:
        raise ApiError(status_code=_status_for_error(exc), code=exc.code, message=str(exc)) from exc


@router.get("/stop", response_model=SessionControlResponse, responses=ERROR_RESPONSES)
async def stop_session(container: AppContainer = Depends(get_container)) -> SessionControlResponse:
    try:
        result = container.session_control.stop()
        return _control_response(result, "Sessão de navegador encerrada com sucesso.")
    except AutomationError as exc:
        raise ApiError(status_code=_status_for_error(exc), code=exc.code, message=str(exc)) from exc


@router.get("/status", response_model=SessionStatusResponse, responses=ERROR_RESPONSES)
async def session_status(container: AppContainer = Depends(get_container)) -> SessionStatusResponse:
    result = container.session_control.status()
    return SessionStatusResponse(
        sessionId=str(result.session_id),
        status=result.status,
        executedOperation=result.executed_operation,
        isOpen=result.is_open,
    )


def _control_response(result, message: str) -> SessionControlResponse:
    return SessionControlResponse(
        sessionId=str(result.session_id),
        status=result.status,
        executedOperation=result.executed_operation,
        isOpen=result.is_open,
        message=message,
    )


def _status_for_error(exc: AutomationError) -> int:
    if isinstance(exc, ExternalServiceError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, (BrowserSessionOpenError, BrowserSessionClosedError)):
        return status.HTTP_409_CONFLICT
    return status.HTTP_500_INTERNAL_SERVER_ERROR
