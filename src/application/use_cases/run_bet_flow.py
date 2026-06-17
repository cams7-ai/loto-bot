"""Caso de uso principal para realizar uma aposta online."""

from __future__ import annotations

import logging

from application.dto import AutomationRunResult
from application.ports import BrowserAutomationPort, NotificationPort
from application.use_cases.session_control import SessionControlUseCase
from domain import AutomationError, AutomationSession
from domain.value_objects import PaymentAuthorization

logger = logging.getLogger(__name__)


class RunBetFlowUseCase:
    def __init__(
        self,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        session_control: SessionControlUseCase,
        payment_authorization: PaymentAuthorization,
    ) -> None:
        self._session = session
        self._browser = browser
        self._notifier = notifier
        self._session_control = session_control
        self._payment_authorization = payment_authorization

    def run(self) -> AutomationRunResult:
        try:
            if not self._session.is_open:
                self._session_control.start()

            self._execute("Seleciona uma modalidade", self._browser.select_lottery_modality)
            self._execute("Escolhe os números da aposta", self._browser.choose_random_numbers)
            self._execute("Adiciona a aposta ao carrinho", self._browser.add_bet_to_cart)
            self._execute("Confirma a compra", self._browser.confirm_purchase)
            self._execute("Seleciona PIX ou cartão", self._browser.select_payment_method)

            self._session.mark_running("Confirma o pagamento")
            self._payment_authorization.require_confirmation()
            self._browser.confirm_payment(self._session)
            logger.info("Operação concluída", extra={"executed_operation": self._session.executed_operation})

            self._session.mark_running("Finaliza a aposta")
            tracking_code = self._browser.finish_bet(self._session)
            self._session.mark_finished(tracking_code)
            self._session_control.close_if_open()
            return AutomationRunResult(
                session_id=self._session.id,
                status="finished",
                message="Aposta finalizada com sucesso.",
                executed_operation="Finaliza a aposta",
                tracking_code=tracking_code,
            )
        except AutomationError as exc:
            return self._handle_failure(exc)
        except Exception as exc:
            logger.exception("Erro inesperado no fluxo de aposta")
            return self._handle_failure(
                AutomationError("Erro inesperado ao executar o fluxo de aposta.", operation=self._session.executed_operation)
            )

    def _execute(self, operation: str, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra={"executed_operation": operation})

    def _handle_failure(self, exc: AutomationError) -> AutomationRunResult:
        operation = exc.operation or self._session.executed_operation or "Operação não identificada"
        self._session.mark_failed(operation)
        message = f"Falha na automação LotoBot durante '{operation}': {exc}"
        logger.error(message, extra={"executed_operation": operation})
        self._notifier.notify_failure(self._session, message)
        self._session_control.close_if_open()
        return AutomationRunResult(
            session_id=self._session.id,
            status="failed",
            message=str(exc),
            executed_operation=operation,
        )
