"""Tratamento de falhas da sessão de automação."""

from __future__ import annotations

import logging

from application.ports import BrowserAutomationPort, NotificationPort
from application.services.playwright_error_message_builder import PlaywrightErrorMessageBuilder
from domain import (
    AutomationError,
    AutomationSession,
    AutomationStatus,
    ErrorMessage,
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

        cls._notify_failure(session, notifier, exc)

        cls._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=str(exc),
            close=close,
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

        error = AutomationError(ErrorMessage.OPERATION_CANNOT_BE_COMPLETED, operation=operation)

        cls._notify_failure(session, notifier, error)

        cls._handle_session_after_failure(
            session=session,
            browser=browser,
            notifier=notifier,
            operation=operation,
            error_message=error_message,
            close=close,
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
    ) -> None:
        if close:
            try:
                cls.close_if_open(session, browser, notifier, operation)
            except Exception:
                logger.error(
                    "Falha ao encerrar sessões após erro de automação",
                    extra=Operation.executed_operation(operation),
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
    ) -> None:
        try:
            if session.status != AutomationStatus.CLOSED:
                try:
                    browser.stop()
                finally:
                    notifier.stop_whatsapp_session(session)
        finally:
            session.mark_closed(operation)

            log_message = "Fechando sessão de navegador aberta"
            log_extra = Operation.executed_operation(session.executed_operation)

            if operation is None:
                logger.info(log_message, extra=log_extra)
            else:
                logger.error(log_message, extra=log_extra)

    @staticmethod
    def _notify_failure(
        session: AutomationSession,
        notifier: NotificationPort,
        error: AutomationError,
    ) -> None:
        try:
            notifier.notify_failure(session.whatsapp_enabled, error)
        except Exception:
            logger.error(
                "Falha ao enviar notificação de erro da automação",
                extra=Operation.executed_operation(error.operation),
            )

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
