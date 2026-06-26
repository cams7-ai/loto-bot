from domain.exceptions.automation_errors import (
    AutomationError,
    ExternalServiceError,
    BrowserSessionOpenError,
    BrowserSessionClosedError,    
    InvalidCPFError,
    InvalidPasswordError,    
    PaymentConfirmationDisabledError,
)

__all__ = [
    "AutomationError",
    "ExternalServiceError",
    "BrowserSessionOpenError",
    "BrowserSessionClosedError",    
    "InvalidCPFError",
    "InvalidPasswordError",    
    "PaymentConfirmationDisabledError",
]
