"""Caso de uso principal para realizar uma aposta ‘online’."""

from __future__ import annotations

from application.dto import AutomationRunResult
from application.ports import BrowserAutomationPort, NotificationPort
from application.services import (
    handle_custom_failure,
    handle_failure,
)
from application.use_cases.operation_executor import OperationExecutor
from domain import (
    AutomationError,
    AutomationSession,
    BrowserSessionClosedError,
    Operation,
    PaymentAuthorization,
)


class RunBetFlowUseCase(OperationExecutor):
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
            raise BrowserSessionClosedError(self._session.executed_operation)

        try:
            self._execute(Operation.ACCESS_HOME, lambda _: self._browser.access_authenticated_home())
            self._execute(Operation.SELECT_LOTTERY_MODALITY, self._browser.select_lottery_modality)
            self._execute(Operation.PLACE_BET, self._browser.place_bet)
            self._execute(Operation.CONFIRM_PAYMENT, self._browser.confirm_purchase)
            self._payment_authorization.require_confirmation()
            self._execute(Operation.CONFIRM_PAYMENT, lambda _: self._browser.confirm_payment())
            self._execute(Operation.CHECK_BET_PROCESSING, self._browser.check_bet_processing)
            self._execute(Operation.CHECK_YOUR_PURCHASES, self._browser.check_your_purchases)
            purchase = self._execute(Operation.COMPLETE_BET, self._browser.finish_bet)
            self._notifier.notify_success(self._session, purchase)
            self._session.mark_finished(self._session.purchase_number)
            return AutomationRunResult(
                session_id=self._session.id,
                status="finished",
                message="Aposta finalizada com sucesso.",
                executed_operation=self._session.executed_operation,
                tracking_code=self._session.purchase_number,
            )

        except AutomationError as exc:
            handle_custom_failure(self._session, self._browser, self._notifier, exc, False)
        except Exception as exc:
            handle_failure(self._session, self._browser, self._notifier, exc, False)
