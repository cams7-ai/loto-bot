"""Caso de uso principal para realizar uma aposta online."""

from __future__ import annotations

import logging

from application.dto import AutomationRunResult
from application.ports import BrowserAutomationPort, NotificationPort
from application.use_cases.session_control import SessionControlUseCase
from domain import (
    Operation,
    AutomationSession,
    AutomationError, 
    BrowserSessionClosedError,      
    PaymentAuthorization,
)

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

            self._execute(Operation.SELECT_LOTTERY_MODALITY, lambda _: self._browser.select_lottery_modality())
            self._execute(Operation.CHOOSE_RANDOM_NUMBERS, lambda _: self._browser.choose_random_numbers())
            self._execute(Operation.ADD_BET_TO_CART, lambda _: self._browser.add_bet_to_cart())
            self._execute(Operation.CONFIRM_PURCHASE, self._browser.confirm_purchase)
            self._execute(Operation.SELECT_PAYMENT_METHOD, lambda _: self._browser.select_payment_method())

            self._session.mark_running(Operation.CONFIRM_PAYMENT)
            self._payment_authorization.require_confirmation()
            self._browser.confirm_payment()
            logger.info("Operação concluída", extra=Operation.executed_operation(self._session.executed_operation))

            self._session.mark_running(Operation.COMPLETE_BET)
            tracking_code = self._browser.finish_bet()
            self._session.mark_finished(tracking_code)
            self._session_control.close_if_open()
            return AutomationRunResult(
                session_id=self._session.id,
                status="finished",
                message="Aposta finalizada com sucesso.",
                executed_operation=self._session.executed_operation,
                tracking_code=tracking_code,
            )
        except AutomationError as exc:
            return self._handle_failure(exc)
        except Exception as exc:
            logger.exception("Erro inesperado no fluxo de aposta")
            return self._handle_failure(
                AutomationError("Erro inesperado ao executar o fluxo de aposta.", operation=self._session.executed_operation)
            )

    def _execute(self, operation: Operation, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra=Operation.executed_operation(operation))

    def _handle_failure(self, exc: AutomationError) -> AutomationRunResult:
        operation = exc.operation or self._session.executed_operation or Operation.UNKNOWN_OPERATION
        self._session.mark_failed(operation)
        message = f"Falha na automação LotoBot durante '{operation.value}': {exc}"
        logger.error(message, extra=Operation.executed_operation(operation))
        self._notifier.notify_failure(self._session, message)
        self._session_control.close_if_open()
        return AutomationRunResult(
            session_id=self._session.id,
            status="failed",
            message=str(exc),
            executed_operation=operation,
        )
