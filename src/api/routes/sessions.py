from __future__ import annotations

from fastapi import APIRouter, Depends

from domain import AutomationError
from api.dependencies import AppContainer, get_container
from api.schemas import (
    ErrorResponse,
    SessionControlResponse,
    SessionStatusResponse,
)
from api.mappers import ApiResponseMapper, ApiExceptionMapper

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Erro de requisição"},
    500: {"model": ErrorResponse, "description": "Erro interno"},
}

@router.get("/start", response_model=SessionControlResponse, responses=ERROR_RESPONSES)
async def start_session(container: AppContainer = Depends(get_container)) -> SessionControlResponse | None:
    try:
        result = container.session_control.start()
        return ApiResponseMapper.session_response(result, "Sessão de navegador iniciada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/stop", response_model=SessionControlResponse, responses=ERROR_RESPONSES)
async def stop_session(container: AppContainer = Depends(get_container)) -> SessionControlResponse | None:
    try:
        result = container.session_control.stop()
        return ApiResponseMapper.session_response(result, "Sessão de navegador encerrada com sucesso")
    except AutomationError as exc:
        ApiExceptionMapper.raise_api_error(exc)


@router.get("/status", response_model=SessionStatusResponse, responses=ERROR_RESPONSES)
async def session_status(container: AppContainer = Depends(get_container)) -> SessionStatusResponse:
    result = container.session_control.status()
    return ApiResponseMapper.session_response(result, "Status da sessão obtido com sucesso")
