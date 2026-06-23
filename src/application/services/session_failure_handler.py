"""Tratamento de falhas da sessão de automação."""

from __future__ import annotations

import logging

from application.notification import build_email_message, build_whatsapp_message
from application.ports import BrowserAutomationPort, NotificationPort
from domain import (
    AutomationError,
    AutomationSession,
    AutomationStatus,
    ErrorCode,
    Operation,
)
from infrastructure import playwright_error_message

logger = logging.getLogger(__name__)

class SessionFailureHandler:
    @staticmethod
    def handle_custom_failure(
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        exc: AutomationError,
        close: bool = True,
    ) -> None:
        operation = session.executed_operation

        logger.error(
            str(exc),
            extra=Operation.executed_operation(operation),
        )

        notification_sent = SessionFailureHandler._notify_failure(
            session=session,
            notifier=notifier,
            operation=operation,
            error_code=exc.code,
        )

        SessionFailureHandler._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=str(exc),
            close=close,
            notification_sent=notification_sent,
        )

        raise exc

    @staticmethod
    def handle_failure(
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        exc: Exception,
        close: bool = True,
    ) -> None:
        operation = session.executed_operation
        error_message = playwright_error_message(operation, str(exc))
        error_code = ErrorCode.AUTOMATION_ERROR_CODE

        logger.error(
            error_message,
            extra=Operation.executed_operation(operation),
        )

        notification_sent = SessionFailureHandler._notify_failure(
            session=session,
            notifier=notifier,
            operation=operation,
            error_code=error_code,
        )

        SessionFailureHandler._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=error_message,
            close=close,
            notification_sent=notification_sent,
        )

        raise AutomationError(error_message, operation=operation) from exc

    @staticmethod
    def close_if_open(
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        operation: Operation | None = None,
        notification_sent: bool = False,
    ) -> None:
        if session.status != AutomationStatus.CLOSED:
            browser.stop()

            if notification_sent:
                notifier.stop_whatsapp_session(session)

        session.mark_closed(operation)

        log_message = "Fechando sessão de navegador aberta"
        log_extra = Operation.executed_operation(session.executed_operation)

        if operation is None:
            logger.info(log_message, extra=log_extra)
        else:
            logger.error(log_message, extra=log_extra)

    @staticmethod
    def failed(
        session: AutomationSession,
        operation: Operation,
        error_message: str,
    ) -> None:
        session.mark_failed(operation)

        logger.error(
            "Falha na automação LotoBot durante '%s': %s",
            operation.value,
            error_message,
            extra=Operation.executed_operation(operation),
        )

    @staticmethod
    def _notify_failure(
        session: AutomationSession,
        notifier: NotificationPort,
        operation: Operation,
        error_code: ErrorCode,
    ) -> bool:
        whatsapp_message = build_whatsapp_message(operation, error_code)
        email_message = build_email_message()

        return notifier.notify_failure(
            session,
            error_code,
            whatsapp_message,
            email_message,
        )

    @staticmethod
    def _handle_session_after_failure(
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        operation: Operation,
        error_message: str,
        close: bool,
        notification_sent: bool,
    ) -> None:
        if close:
            SessionFailureHandler.close_if_open(
                session=session,
                browser=browser,
                notifier=notifier,
                operation=operation,
                notification_sent=notification_sent,
            )
            return

        SessionFailureHandler.failed(
            session=session,
            operation=operation,
            error_message=error_message,
        )