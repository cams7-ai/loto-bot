from domain.exceptions.automation_errors import (
    AutomationError,
    ExternalServiceError,
    BrowserSessionOpenError,
    BrowserSessionClosedError,
    PageRedirectionError,
    InvalidCPFError,
    InvalidPasswordError,    
    PaymentConfirmationDisabledError,
    IndividualBetRegistrationClosedError,
    BetTemporarilyDisabledError,
    DailyPurchaseLimitError,
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
]
