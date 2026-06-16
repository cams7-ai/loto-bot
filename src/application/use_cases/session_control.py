"""Casos de uso para controle de sessão."""

from __future__ import annotations

import logging

from application.dto import SessionStatusResult
from application.ports import BrowserAutomationPort, NotificationPort
from domain import AutomationSession, BrowserSessionClosedError, BrowserSessionOpenError

logger = logging.getLogger(__name__)


class SessionControlUseCase:
    def __init__(
        self,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
    ) -> None:
        self._session = session
        self._browser = browser
        self._notifier = notifier

    def start(self) -> SessionStatusResult:
        if self._session.is_open:
            raise BrowserSessionOpenError("Já existe uma sessão de navegador aberta.")

        tab_id = self._browser.start(self._session)
        self._session.mark_open(tab_id)
        self._notifier.start_whatsapp_session(self._session)
        logger.info("Sessão de navegador iniciada", extra={"executed_operation": "Inicia sessão"})
        return self.status()

    def stop(self) -> SessionStatusResult:
        if not self._session.is_open:
            raise BrowserSessionClosedError("A sessão de navegador já está fechada.")

        self._browser.stop()
        self._notifier.stop_whatsapp_session(self._session)
        self._session.mark_closed()
        logger.info("Sessão de navegador encerrada", extra={"executed_operation": "Fecha sessão"})
        return self.status()

    def close_if_open(self) -> None:
        if self._session.status.value != "closed":
            self._browser.stop()
            self._notifier.stop_whatsapp_session(self._session)
        self._session.mark_closed()

    def status(self) -> SessionStatusResult:
        return SessionStatusResult(
            session_id=self._session.id,
            status=self._session.status.value,
            executed_operation=self._session.executed_operation,
            is_open=self._session.is_open,
        )
