"""Caso de uso principal para realizar uma aposta ‘online’."""

from __future__ import annotations

import logging

from domain import (
    Operation,
    AutomationSession,
    AutomationError,
    BrowserSessionClosedError,
    PaymentAuthorization,
)
from application.dto import AutomationRunResult
from application.ports import BrowserAutomationPort, NotificationPort
from application.services import (
    handle_failure,
    handle_custom_failure,
    close_if_open,
)

logger = logging.getLogger(__name__)


class RunBetFlowUseCase:
    def __init__(
        self,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        payment_authorization: PaymentAuthorization,
    ) -> None:
        self._session = session
        self._browser = browser
        self._notifier = notifier
        self._payment_authorization = payment_authorization

    def run(self) -> AutomationRunResult | None:
        if not self._session.is_open:
            raise BrowserSessionClosedError("A sessão de navegador já está fechada")

        try:
            self._execute(Operation.ACCESS_HOME, lambda _: self._browser.access_home(False))
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
            close_if_open(self._session, self._browser, self._notifier, None,True)
            return AutomationRunResult(
                session_id=self._session.id,
                status="finished",
                message="Aposta finalizada com sucesso.",
                executed_operation=self._session.executed_operation,
                tracking_code=tracking_code,
            )

        except AutomationError as exc:
            handle_custom_failure(self._session, self._browser, self._notifier, exc, False)
        except Exception as exc:
            handle_failure(self._session, self._browser, self._notifier, exc, False)

    def _execute(self, operation: Operation, action) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logger.info("Operação concluída", extra=Operation.executed_operation(operation))

