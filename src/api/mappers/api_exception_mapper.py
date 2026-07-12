from __future__ import annotations

from api.exceptions import ApiError
from domain import AutomationError


class ApiExceptionMapper:
    @classmethod
    def raise_api_error(cls, exc: AutomationError) -> None:
        raise ApiError(
            status_code=exc.status_code.value,
            code=exc.code,
            message=str(exc),
        ) from exc
