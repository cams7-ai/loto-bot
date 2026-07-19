"""Caso de uso principal para realizar uma aposta ‘online’."""

from __future__ import annotations

import logging

from application.dto import AutomationRunResult, PurchaseResult
from application.ports import BrowserAutomationPort, NotificationPort
from application.services import (
    PlacedBetService,
    handle_custom_failure,
    handle_failure,
)
from application.use_cases.operation_executor import OperationExecutor
from domain import (
    LOTTERY_MODALITY_NOT_FOUND,
    SUPPORTED_BET_RUN_LOTTERY_MODALITIES,
    AutomationError,
    AutomationSession,
    BrowserSessionClosedError,
    LotteryModality,
    Operation,
    PaymentAuthorization,
)

logger = logging.getLogger(__name__)


class RunBetFlowUseCase(OperationExecutor):
    def __init__(
        self,
        session: AutomationSession,
        browser: BrowserAutomationPort,
        notifier: NotificationPort,
        payment_authorization: PaymentAuthorization,
        bet_persistence: PlacedBetService | None = None,
        selected_lottery_modality: str = "mega-sena",
    ) -> None:
        self._session = session
        self._browser = browser
        self._notifier = notifier
        self._payment_authorization = payment_authorization
        self._bet_persistence = bet_persistence
        self._selected_lottery_modality = selected_lottery_modality

    def run(self, selected_lottery_modality: LotteryModality | None = None) -> AutomationRunResult | None:
        if not self._session.is_open:
            raise BrowserSessionClosedError(self._session.executed_operation)

        try:
            lottery_modality = self._resolve_lottery_modality(selected_lottery_modality)
            self._execute(Operation.ACCESS_HOME, lambda _: self._browser.access_authenticated_home())
            self._execute(
                Operation.SELECT_LOTTERY_MODALITY,
                lambda session: self._browser.select_lottery_modality(session, lottery_modality),
            )
            self._execute(Operation.PLACE_BET, lambda session: self._browser.place_bet(session, lottery_modality))
            self._execute(Operation.CONFIRM_PAYMENT, self._browser.confirm_purchase)
            self._payment_authorization.require_confirmation()
            self._execute(Operation.CONFIRM_PAYMENT, lambda _: self._browser.confirm_payment())
            self._execute(Operation.CHECK_BET_PROCESSING, self._browser.check_bet_processing)
            purchase_number = self._execute(Operation.CHECK_YOUR_PURCHASES, self._browser.check_your_purchases)
            purchase = self._execute(
                Operation.COMPLETE_BET,
                lambda session: self._browser.finish_bet(session, lottery_modality),
            )
            self._persist_purchase(purchase, lottery_modality)
            self._notifier.notify_success(self._session, purchase)
            self._session.mark_finished()
            return AutomationRunResult(
                session_id=self._session.id,
                status="finished",
                message="Aposta finalizada com sucesso.",
                executed_operation=self._session.executed_operation,
                purchase_number=purchase_number,
            )

        except AutomationError as exc:
            handle_custom_failure(self._session, self._browser, self._notifier, exc, False)
        except Exception as exc:
            handle_failure(self._session, self._browser, self._notifier, exc, False)

    def _resolve_lottery_modality(self, selected_lottery_modality: LotteryModality | None) -> LotteryModality:
        lottery_modality = selected_lottery_modality or LotteryModality.from_string(self._selected_lottery_modality)
        if lottery_modality is None or lottery_modality not in SUPPORTED_BET_RUN_LOTTERY_MODALITIES:
            raise AutomationError(
                LOTTERY_MODALITY_NOT_FOUND.format(modality=self._selected_lottery_modality),
                operation=Operation.SELECT_LOTTERY_MODALITY,
            )
        return lottery_modality

    def _persist_purchase(self, purchase: PurchaseResult, lottery_modality: LotteryModality) -> None:
        if self._bet_persistence is None:
            return

        try:
            self._bet_persistence.save(purchase, lottery_modality)
        except Exception:
            logger.exception("Falha ao persistir aposta finalizada.")
