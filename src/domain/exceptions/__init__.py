from domain.exceptions.automation_errors import (
    AutomationError,
    BetsNotAvailableForCaptureError,
    BetTemporarilyDisabledError,
    BrowserSessionClosedError,
    BrowserSessionOpenError,
    DailyPurchaseLimitError,
    ExternalServiceError,
    IndividualBetRegistrationClosedError,
    InvalidCPFError,
    InvalidPasswordError,
    PageRedirectionError,
    PaymentConfirmationDisabledError,
)

__all__ = [
    "AutomationError",
    "ExternalServiceError",
    "BrowserSessionOpenError",
    "BrowserSessionClosedError",
    "PageRedirectionError",
    "InvalidCPFError",
    "InvalidPasswordError",
    "PaymentConfirmationDisabledError",
    "IndividualBetRegistrationClosedError",
    "BetTemporarilyDisabledError",
    "DailyPurchaseLimitError",
    "BetsNotAvailableForCaptureError",
]
