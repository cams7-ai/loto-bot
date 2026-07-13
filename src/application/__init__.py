from application.dto import AutomationRunResult, BetResult, PurchaseResult, SessionStatusResult
from application.notification import (
    build_email_message,
    build_success_email_message,
    build_success_whatsapp_message,
    build_whatsapp_message,
    get_error_message,
)
from application.ports import BrowserAutomationPort, NotificationPort, ValidationCodePort
from application.services import close_if_open, handle_custom_failure, handle_failure
from application.use_cases import RunBetFlowUseCase, SessionControlUseCase

__all__ = [
    "AutomationRunResult",
    "BetResult",
    "PurchaseResult",
    "SessionStatusResult",
    "BrowserAutomationPort",
    "NotificationPort",
    "ValidationCodePort",
    "build_email_message",
    "build_success_email_message",
    "build_success_whatsapp_message",
    "build_whatsapp_message",
    "get_error_message",
    "handle_failure",
    "handle_custom_failure",
    "close_if_open",
    "RunBetFlowUseCase",
    "SessionControlUseCase",
]
