"""Exceções HTTP da API."""

from domain import ErrorCode


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        message: str | None = None,
        messages: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.messages = list(messages) if messages is not None else None
        self.fields = fields
        super().__init__(message or "; ".join(self.messages or []))
