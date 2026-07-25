"""Exceções HTTP da API."""

from typing import Any

from domain import ErrorCode


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        message: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = list(details) if details is not None else None
        super().__init__(message or "")
