"""Exceções de domínio da automação."""

from __future__ import annotations

from enum import StrEnum

from domain.exceptions.error_code import ErrorCode

class AutomationError(RuntimeError):
    code = ErrorCode.AUTOMATION_ERROR_CODE.value

    def __init__(self, message: str, *, operation: StrEnum | str = "Operação não identificada") -> None:
        self.operation = operation.value if isinstance(operation, StrEnum) else operation
        super().__init__(message)

class BrowserSessionOpenError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE.value

class BrowserSessionClosedError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE.value

class PaymentConfirmationDisabledError(AutomationError):
    code = ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE.value

class ExternalServiceError(AutomationError):
    code = ErrorCode.EXTERNAL_SERVICE_ERROR_CODE.value
