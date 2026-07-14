from __future__ import annotations

from api.schemas import SessionControlResponse
from application import SessionStatusResult


class ApiResponseMapper:
    @staticmethod
    def session_response(result: SessionStatusResult, message: str) -> SessionControlResponse:
        return SessionControlResponse(
            session_id=str(result.session_id),
            status=result.status,
            executed_operation=result.executed_operation.value,
            is_open=result.is_open,
            message=message,
        )
