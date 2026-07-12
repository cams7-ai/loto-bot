"""Exceções de domínio da automação."""

from __future__ import annotations

from domain.enums import Operation, ErrorCode
from domain.constants import (
    BROWSER_SESSION_OPEN,
    BROWSER_SESSION_CLOSED,
    PAGE_REDIRECTION_ERROR,
    INVALID_CPF,
    INVALID_PASSWORD,
    PAYMENT_CONFIRMATION_DISABLED,
    INDIVIDUAL_BET_REGISTRATION_CLOSED,
    BET_TEMPORARILY_DISABLED,
    DAILY_PURCHASE_LIMIT,
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

class PageRedirectionError(AutomationError):
    code = ErrorCode.PAGE_REDIRECTION_ERROR_CODE

    def __init__(self, path: str, operation: Operation = Operation.UNKNOWN_OPERATION) -> None:
        super().__init__(message=f"{PAGE_REDIRECTION_ERROR.format(path=path)}", operation=operation)

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

    def __init__(self) -> None:
        super().__init__(message=PAYMENT_CONFIRMATION_DISABLED, operation=Operation.CONFIRM_PAYMENT)

class IndividualBetRegistrationClosedError(AutomationError):
    code = ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE

    def __init__(self) -> None:
        super().__init__(message=INDIVIDUAL_BET_REGISTRATION_CLOSED, operation=Operation.SELECT_LOTTERY_MODALITY)

class BetTemporarilyDisabledError(AutomationError):
    code = ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE

    def __init__(self, lottery_modality: str) -> None:
        super().__init__(message=f"{BET_TEMPORARILY_DISABLED.format(modality=lottery_modality)}", operation=Operation.SELECT_LOTTERY_MODALITY)

class DailyPurchaseLimitError(AutomationError):
    code = ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE

    def __init__(self) -> None:
        super().__init__(message=DAILY_PURCHASE_LIMIT, operation=Operation.CONFIRM_PAYMENT)


