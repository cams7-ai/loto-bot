"""Casos de uso para controle de sessão."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from time import sleep

from application.dto import SessionStatusResult
from application.ports import BrowserAutomationPort, NotificationPort, ValidationCodePort
from domain import AutomationError, AutomationSession, BrowserSessionClosedError, BrowserSessionOpenError

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
            raise BrowserSessionOpenError("Já existe uma sessão de navegador aberta.")

        tab_id = self._browser.start(self._session)
        self._session.mark_open(tab_id)
        self._notifier.start_whatsapp_session(self._session)
        logger.info("Sessão de navegador iniciada", extra={"executed_operation": "Inicia sessão"})
        try:
            self._authenticate()
        except AutomationError:
            self.close_if_open()
            raise
        except Exception as exc:
            logger.exception("Erro inesperado no processo de autenticação")
            operation = self._session.executed_operation or "Autenticação"
            self.close_if_open()
            raise AutomationError("Erro inesperado ao autenticar a sessão.", operation=operation) from exc

        self._session.mark_open(self._session.tab_id)
        return self.status()

    def _authenticate(self) -> None:
        self._execute("Acessa o site Loterias Online CAIXA", self._browser.access_lottery_portal)
        if self._is_authenticated():
            return
        self._execute("Aceita os termos de uso", self._browser.accept_terms)
        self._execute("Home", self._browser.access_home)
        self._execute("Informa o CPF", self._browser.submit_cpf)

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-validation-code") as executor:
            validation_code_request_started = Event()
            validation_code = self._request_validation_code_async(executor, validation_code_request_started)
            validation_code_request_started.wait()
            sleep(VALIDATION_CODE_LOOKUP_LEAD_SECONDS)
            self._execute("Solicita o código de acesso", self._browser.request_validation_code)
            self._session.valid_code = validation_code.result()
        self._execute_with_code("Informa o código recebido")

        self._execute("Informa a senha", self._browser.submit_password)

    def _execute(self, operation: str, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra={"executed_operation": operation})

    def _is_authenticated(self) -> bool:
        operation = "Verifica se a sessão está autenticada"
        self._session.mark_running(operation)
        authenticated = self._browser.is_authenticated(self._session)
        logger.info("Operação concluída", extra={"executed_operation": operation})
        return authenticated

    def _execute_with_code(self, operation: str) -> None:
        self._session.mark_running(operation)
        self._browser.submit_validation_code(self._session, self._session.valid_code or "")
        logger.info("Operação concluída", extra={"executed_operation": operation})

    def _request_validation_code_async(self, executor: ThreadPoolExecutor, request_started: Event) -> Future[str]:
        return executor.submit(self._get_validation_code, request_started)

    def _get_validation_code(self, request_started: Event) -> str:
        request_started.set()
        return self._validation_codes.get_validation_code()

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
