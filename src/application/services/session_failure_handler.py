"""Tratamento de falhas da sessão de automação."""

from __future__ import annotations

import logging

from application.ports import BrowserAutomationPort, NotificationPort
from application.services.playwright_error_message_builder import PlaywrightErrorMessageBuilder
from domain import (
    OPERATION_CANNOT_BE_COMPLETED,
    AutomationError,
    AutomationSession,
    AutomationStatus,
    Operation,
)

logger = logging.getLogger(__name__)


class SessionFailureHandler:
    @classmethod
    def handle_custom_failure(
        cls,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        exc: AutomationError,
        close: bool = True,
    ) -> None:
        operation = exc.operation

        logger.error(
            str(exc),
            extra=Operation.executed_operation(operation),
        )

        notification_sent = notifier.notify_failure(session.whatsapp_enabled, exc)

        cls._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=str(exc),
            close=close,
            notification_sent=notification_sent,
        )

        raise exc

    @classmethod
    def handle_failure(
        cls,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        exc: Exception,
        close: bool = True,
    ) -> None:
        operation = session.executed_operation
        error_message = PlaywrightErrorMessageBuilder.build_error_message(operation, str(exc))

        logger.error(
            error_message,
            extra=Operation.executed_operation(operation),
        )

        error = AutomationError(OPERATION_CANNOT_BE_COMPLETED, operation=operation)

        notification_sent = notifier.notify_failure(session.whatsapp_enabled, error)

        cls._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=error_message,
            close=close,
            notification_sent=notification_sent,
        )

        raise error from exc

    @classmethod
    def _handle_session_after_failure(
        cls,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        operation: Operation,
        error_message: str,
        close: bool,
        notification_sent: bool,
    ) -> None:
        if close:
            cls.close_if_open(
                session=session,
                browser=browser,
                notifier=notifier,
                operation=operation,
                notification_sent=notification_sent,
            )
            return

        cls._failed(
            session=session,
            operation=operation,
            error_message=error_message,
        )

    @classmethod
    def close_if_open(
        cls,
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

    @classmethod
    def _failed(
        cls,
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
