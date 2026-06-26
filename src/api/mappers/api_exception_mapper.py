from __future__ import annotations

from fastapi import status

from api.exceptions import ApiError
from domain import (
    AutomationError,
    ExternalServiceError,
    BrowserSessionOpenError,
    BrowserSessionClosedError,    
    InvalidCPFError,
    InvalidPasswordError,    
)

class ApiExceptionMapper:
    @staticmethod
    def raise_api_error(exc: AutomationError) -> None:
        raise ApiError(
            status_code=ApiExceptionMapper._status_for_error(exc),
            code=exc.code,
            message=str(exc),
        ) from exc

    @staticmethod
    def _status_for_error(exc: AutomationError) -> int:
        if isinstance(exc, ExternalServiceError):
            # Quando o serviço externo está indisponível
            return status.HTTP_503_SERVICE_UNAVAILABLE         

        if isinstance(exc, (BrowserSessionOpenError, BrowserSessionClosedError)):
            # Quando a sessão já está aberta ou fechada
            return status.HTTP_409_CONFLICT
        
        if isinstance(exc, (InvalidCPFError, InvalidPasswordError)):
            return status.HTTP_400_BAD_REQUEST

        # Outros erros de automação
        return status.HTTP_500_INTERNAL_SERVER_ERROR