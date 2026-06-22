"""Casos de uso para controle de sessão."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from time import sleep

from application.dto import SessionStatusResult
from application.ports import BrowserAutomationPort, NotificationPort, ValidationCodePort
from domain import (
    Operation,
    AutomationSession,
    AutomationError, 
    BrowserSessionClosedError, 
    BrowserSessionOpenError,     
)

logger = logging.getLogger(__name__)
VALIDATION_CODE_LOOKUP_LEAD_SECONDS = 1


class SessionControlUseCase:
    def __init__(
        self,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        validation_codes: ValidationCodePort,
        notifier: NotificationPort,
    ) -> None:
        self._session = session
        self._browser = browser
        self._validation_codes = validation_codes
        self._notifier = notifier

    def start(self) -> SessionStatusResult:
        if self._session.is_open:
            raise BrowserSessionOpenError("Já existe uma sessão de navegador aberta")

        tab_id = self._browser.start(self._session)
        self._session.mark_open(tab_id)
        self._notifier.start_whatsapp_session(self._session)
        logger.info("Sessão de navegador iniciada", extra=Operation.executed_operation(self._session.executed_operation))
        try:
            if self._authenticate():
                self._disable_notification(Operation.ACCESS_HOME)
                logger.info("Sessão de navegador autenticada", extra=Operation.executed_operation(self._session.executed_operation))
        except AutomationError:
            self.close_if_open()
            raise
        except Exception as exc:
            error_message = "Erro inesperado ao autenticar a sessão"
            logger.exception(error_message)
            self.close_if_open()
            raise AutomationError(error_message, operation=self._session.executed_operation) from exc

        self._session.mark_open(self._session.tab_id)
        return self.status()

    def _disable_notification(self, operation: Operation) -> None:
        self._session.mark_running(operation)
        self._browser.disable_notification()

    def close_if_open(self) -> None:
        if self._session.status.value != "closed":
            self._browser.stop()
            self._notifier.stop_whatsapp_session(self._session)
            logger.debug("Fechando sessão de navegador aberta", extra=Operation.executed_operation(self._session.executed_operation))
        self._session.mark_closed()

    def _authenticate(self) -> bool:
        self._execute(Operation.ACCESS_LOTTERY_PORTAL, lambda _: self._browser.access_home())
        if self._browser.is_authenticated(False):
            return True

        self._execute(Operation.ACCEPT_TERMS, lambda _: self._browser.accept_terms())
        self._execute(Operation.ACCESS_HOME, lambda _: self._browser.access_home())
        self._execute(Operation.SUBMIT_CPF, self._browser.submit_cpf)

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-validation-code") as executor:
            operation = Operation.REQUEST_VALIDATION_CODE
            validation_code_request_started = Event()
            validation_code = self._request_validation_code_async(executor, validation_code_request_started, operation)
            validation_code_request_started.wait()
            sleep(VALIDATION_CODE_LOOKUP_LEAD_SECONDS)
            self._execute(operation, self._browser.request_validation_code)
            self._session.valid_code = validation_code.result()

        self._execute(Operation.SUBMIT_VALIDATION_CODE, self._submit_validation_code)
        self._execute(Operation.SUBMIT_PASSWORD, self._browser.submit_password)

        return self._browser.is_authenticated(True)

    def _request_validation_code_async(self, executor: ThreadPoolExecutor, request_started: Event, operation: Operation) -> Future[str]:
        return executor.submit(self._get_validation_code, request_started, operation)

    def _get_validation_code(self, request_started: Event, operation: Operation) -> str:
        request_started.set()
        return self._validation_codes.get_validation_code(operation)

    def _submit_validation_code(self, session: AutomationSession) -> None:
        self._browser.submit_validation_code(session, self._session.valid_code or "")

    def _execute(self, operation: Operation, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra=Operation.executed_operation(operation))

    def stop(self) -> SessionStatusResult:
        if not self._session.is_open:
            raise BrowserSessionClosedError("A sessão de navegador já está fechada")

        self._browser.stop()
        self._session.mark_closed()
        self._notifier.stop_whatsapp_session(self._session)
        logger.info("Sessão de navegador encerrada", extra=Operation.executed_operation(self._session.executed_operation))
        return self.status()

    def status(self) -> SessionStatusResult:
        return SessionStatusResult(
            session_id=self._session.id,
            status=self._session.status.value,
            executed_operation=self._session.executed_operation,
            is_open=self._session.is_open,
        )
