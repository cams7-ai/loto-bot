"""Tratamento de falhas da sessão de automação."""

from __future__ import annotations

import logging

from application.ports import BrowserAutomationPort, NotificationPort
from domain import (
    OPERATION_CANNOT_BE_COMPLETED,
    AutomationSession,
    AutomationStatus,
    Operation,
    AutomationError,
)
from infrastructure import playwright_error_message

logger = logging.getLogger(__name__)

class SessionFailureHandler:
    @staticmethod
    def handle_custom_failure(
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        error: AutomationError,
        close: bool = True,
    ) -> None:
        operation = error.operation

        logger.error(
            str(error),
            extra=Operation.executed_operation(operation),
        )

        notification_sent = notifier.notify_failure(session.whatsapp_enabled, error)

        SessionFailureHandler._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=str(error),
            close=close,
            notification_sent=notification_sent,
        )

        raise error

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

        logger.error(
            error_message,
            extra=Operation.executed_operation(operation),
        )

        error = AutomationError(OPERATION_CANNOT_BE_COMPLETED, operation=operation)

        notification_sent = notifier.notify_failure(session.whatsapp_enabled, error)

        SessionFailureHandler._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=error_message,
            close=close,
            notification_sent=notification_sent,
        )

        raise error from exc

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