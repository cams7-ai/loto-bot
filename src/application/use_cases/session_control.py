"""Casos de uso para controle de sessão."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from domain import (
    Operation,
    AutomationSession,
    AutomationError,
    BrowserSessionOpenError,
    BrowserSessionClosedError,    
    InvalidCPFError,
)
from application.dto import SessionStatusResult
from application.ports import BrowserAutomationPort, NotificationPort, ValidationCodePort
from application.services import (
    handle_failure,
    handle_custom_failure,
    close_if_open
)

logger = logging.getLogger(__name__)

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
            raise BrowserSessionOpenError(self._session.executed_operation)

        tab_id = self._browser.start(self._session)
        self._session.mark_open(tab_id)
        self._notifier.start_whatsapp_session(self._session)
        logger.info("Sessão de navegador iniciada", extra=Operation.executed_operation(self._session.executed_operation))
        try:
            if self._authenticate():
                self._execute(Operation.SHOPPING_CART, self._browser.clear_shopping_cart)
                logger.info("Sessão de navegador autenticada", extra=Operation.executed_operation(self._session.executed_operation))
        except AutomationError as exc:
            handle_custom_failure(self._session, self._browser, self._notifier, exc)
        except Exception as exc:
            handle_failure(self._session, self._browser, self._notifier, exc)

        self._session.mark_open(self._session.tab_id)
        return self.status()

    def _authenticate(self) -> bool:
        self._execute(Operation.ACCESS_LOTTERY_PORTAL, lambda _: self._browser.access_home())
        if self._browser.is_authenticated():
            return True

        self._execute(Operation.ACCEPT_TERMS, self._browser.accept_terms)
        self._execute(Operation.ACCESS_HOME, lambda _: self._browser.access_home())
        self._execute(Operation.SUBMIT_CPF, self._browser.submit_cpf)

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-validation-code") as executor:
            operation = Operation.REQUEST_VALIDATION_CODE
            validation_code_request_started = Event()
            validation_code = self._request_validation_code_async(executor, validation_code_request_started, operation)
            self._wait_for_validation_code_request_start(validation_code_request_started)
            self._execute(operation, self._browser.request_validation_code)
            self._session.valid_code = validation_code.result()

        self._execute(Operation.SUBMIT_VALIDATION_CODE, self._submit_validation_code)
        self._execute(Operation.SUBMIT_PASSWORD, self._browser.submit_password)

        return self._browser.is_already_authenticated()

    def _request_validation_code_async(self, executor: ThreadPoolExecutor, request_started: Event, operation: Operation) -> Future[str]:
        if not self._browser.is_valid_cpf():
            raise InvalidCPFError()

        return executor.submit(self._get_validation_code, request_started, operation)

    def _get_validation_code(self, request_started: Event, operation: Operation) -> str:
        request_started.set()
        return self._validation_codes.get_validation_code(operation)

    def _wait_for_validation_code_request_start(self, request_started: Event) -> None:
        started_at = monotonic()
        request_started.wait()
        remaining_milliseconds = self._browser.validation_code_lookup_lead() - ((monotonic() - started_at) * 1000)
        if remaining_milliseconds > 0:
            sleep(remaining_milliseconds / 1000)

    def _submit_validation_code(self, session: AutomationSession) -> None:
        self._browser.submit_validation_code(session, self._session.valid_code or "")

    def _execute(self, operation: Operation, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra=Operation.executed_operation(operation))

    def stop(self) -> SessionStatusResult:
        if not self._session.is_open:
            raise BrowserSessionClosedError(self._session.executed_operation)

        self._close()
        return self.status()

    def _close(self) -> None:
        close_if_open(self._session, self._browser, self._notifier, None,True)

    def status(self) -> SessionStatusResult:
        return SessionStatusResult(
            session_id=self._session.id,
            status=self._session.status.value,
            executed_operation=self._session.executed_operation,
            is_open=self._session.is_open,
        )
