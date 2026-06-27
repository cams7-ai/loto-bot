from domain.enums import (
    Operation,
    ErrorCode,
    WhatsAppSessionStatus,
    WhatsAppMessageStatus,
)
from domain.constants import (
    OPERATION_CANNOT_BE_COMPLETED,
    FALLBACK_EMAIL_SEND_FAILED,
    VALIDATION_CODE_FETCH_TIMEOUT,
    VALIDATION_CODE_FETCH_FAILED,
    GMAIL_READER_API_VALIDATION_CODE_NOT_RETURNED,
    BROWSER_SESSION_OPEN,
    BROWSER_SESSION_CLOSED,
    INVALID_CPF,
    INVALID_PASSWORD,
    PAYMENT_CONFIRMATION_DISABLED,
)
from domain.entities import (
    AutomationSession,
    AutomationStatus,
)
from domain.exceptions import (
    AutomationError,
    ExternalServiceError,
    BrowserSessionOpenError,
    BrowserSessionClosedError,    
    InvalidCPFError,
    InvalidPasswordError,    
    PaymentConfirmationDisabledError,
)
from domain.value_objects import PaymentAuthorization

__all__ = [
    "Operation",
    "ErrorCode",
    "WhatsAppSessionStatus",
    "WhatsAppMessageStatus",
    "OPERATION_CANNOT_BE_COMPLETED",
    "FALLBACK_EMAIL_SEND_FAILED",
    "VALIDATION_CODE_FETCH_TIMEOUT",
    "VALIDATION_CODE_FETCH_FAILED",
    "GMAIL_READER_API_VALIDATION_CODE_NOT_RETURNED",
    "BROWSER_SESSION_OPEN",
    "BROWSER_SESSION_CLOSED",
    "INVALID_CPF",
    "INVALID_PASSWORD",
    "PAYMENT_CONFIRMATION_DISABLED",
    "AutomationSession",
    "AutomationStatus",
    "AutomationError",
    "ExternalServiceError",
    "BrowserSessionOpenError",
    "BrowserSessionClosedError",    
    "InvalidCPFError",
    "InvalidPasswordError",    
    "PaymentConfirmationDisabledError",
    "PaymentAuthorization",
]
