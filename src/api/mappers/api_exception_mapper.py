from __future__ import annotations

from api.exceptions import ApiError
from application import PortalBetFiltersValidationError, ValidationErrorDetail
from domain import AutomationError, ErrorCode


class ApiExceptionMapper:
    @classmethod
    def raise_api_error(cls, exc: AutomationError) -> None:
        raise ApiError(
            status_code=exc.status_code.value,
            code=exc.code,
            message=str(exc),
        ) from exc

    @classmethod
    def raise_internal_server_error(cls, message: str) -> None:
        raise ApiError(
            status_code=500,
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
        )

    @classmethod
    def raise_bad_request(cls, exc: ValueError) -> None:
        raise ApiError(
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
            message=str(exc),
        ) from exc

    @classmethod
    def raise_invalid_parameters(cls, exc: PortalBetFiltersValidationError) -> None:
        raise ApiError(
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
            message="Parâmetros inválidos",
            details=[detail.to_dict() for detail in exc.details],
        ) from exc

    @classmethod
    def raise_invalid_fields(cls, details: list[ValidationErrorDetail]) -> None:
        raise ApiError(
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
            message="Campos inválidos",
            details=[detail.to_dict() for detail in details],
        )
