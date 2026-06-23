"""Exceções de domínio da automação."""

from __future__ import annotations

from domain.enums import Operation, ErrorCode

class AutomationError(RuntimeError):
    code = ErrorCode.AUTOMATION_ERROR_CODE

    def __init__(self, message: str, *, operation: Operation = Operation.UNKNOWN_OPERATION) -> None:
        self.operation = operation
        super().__init__(message)

class BrowserSessionOpenError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE

class BrowserSessionClosedError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE

class PaymentConfirmationDisabledError(AutomationError):
    code = ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE

class ExternalServiceError(AutomationError):
    code = ErrorCode.EXTERNAL_SERVICE_ERROR_CODE
