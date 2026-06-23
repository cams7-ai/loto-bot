from __future__ import annotations

from application import SessionStatusResult
from api.schemas import SessionControlResponse

class ApiResponseMapper:
    @staticmethod
    def session_response(result: SessionStatusResult, message: str) -> SessionControlResponse:
        return SessionControlResponse(
            sessionId=str(result.session_id),
            status=result.status,
            executedOperation=result.executed_operation.value,
            isOpen=result.is_open,
            message=message,
        )