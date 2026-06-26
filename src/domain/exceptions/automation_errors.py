"""Exceções de domínio da automação."""

from __future__ import annotations

from domain.enums import Operation, ErrorCode
from domain.constants import (
    BROWSER_SESSION_OPEN,
    BROWSER_SESSION_CLOSED,
    INVALID_CPF,
    INVALID_PASSWORD,
)

class AutomationError(RuntimeError):
    code = ErrorCode.AUTOMATION_ERROR_CODE

    def __init__(self, message: str, *, operation: Operation = Operation.UNKNOWN_OPERATION) -> None:
        self.operation = operation
        super().__init__(message)

class ExternalServiceError(AutomationError):
    code = ErrorCode.EXTERNAL_SERVICE_ERROR_CODE

class BrowserSessionOpenError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE

    def __init__(self, operation: Operation = Operation.UNKNOWN_OPERATION) -> None:
        super().__init__(message=BROWSER_SESSION_OPEN, operation=operation)

class BrowserSessionClosedError(AutomationError):
    code = ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE

    def __init__(self, operation: Operation = Operation.UNKNOWN_OPERATION) -> None:
        super().__init__(message=BROWSER_SESSION_CLOSED, operation=operation)

class InvalidCPFError(AutomationError):
    code = ErrorCode.INVALID_CPF_ERROR_CODE

    def __init__(self) -> None:
        super().__init__(message=INVALID_CPF, operation=Operation.SUBMIT_CPF)

class InvalidPasswordError(AutomationError):
    code = ErrorCode.INVALID_PASSWORD_ERROR_CODE

    def __init__(self) -> None:
        super().__init__(message=INVALID_PASSWORD, operation=Operation.SUBMIT_PASSWORD)

class PaymentConfirmationDisabledError(AutomationError):
    code = ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE


