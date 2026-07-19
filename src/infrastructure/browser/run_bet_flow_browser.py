"""Operações Playwright usadas pelo fluxo de aposta."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from playwright.sync_api import Page

from application.dto import BetResult, PurchaseResult
from domain import (
    LOTTERY_MODALITY_NOT_FOUND,
    AutomationError,
    AutomationSession,
    BetsNotAvailableForCaptureError,
    BetTemporarilyDisabledError,
    BrlCurrencyFormatter,
    DailyPurchaseLimitError,
    IndividualBetRegistrationClosedError,
    LotteryModality,
    Operation,
    PageRedirectionError,
)
from infrastructure.browser.playwright_common import PlaywrightBrowserBase
from infrastructure.browser.portal_data import Bet, PurchaseDetails, PurchaseTotals
from infrastructure.selectors import Selectors, get_lottery_modality

logger = logging.getLogger(__name__)


class RunBetFlowBrowserMixin(PlaywrightBrowserBase):
    def select_lottery_modality(self, session: AutomationSession, lottery_modality: LotteryModality) -> None:
        self._run_on_browser_thread(self._select_lottery_modality, session, lottery_modality)

    def _select_lottery_modality(self, session: AutomationSession, lottery_modality: LotteryModality) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.home_path)
        selector = Selectors.modality_button(lottery_modality.value)
        if selector is None:
            raise AutomationError(
                LOTTERY_MODALITY_NOT_FOUND.format(modality=lottery_modality.value),
                operation=Operation.SELECT_LOTTERY_MODALITY,
            )

        if not self._click(page, short_timeout_ms, selector):
            selector = Selectors.disabled_modality_button(lottery_modality.value)
            if selector is not None and self._click(page, short_timeout_ms, selector):
                raise BetTemporarilyDisabledError(lottery_modality.value)

        if self._click(page, short_timeout_ms, Selectors.CLOSE_BET_REGISTRATION_ALERT_BUTTON):
            raise IndividualBetRegistrationClosedError()

    def place_bet(self, session: AutomationSession, lottery_modality: LotteryModality) -> None:
        self._run_on_browser_thread(self._place_bet, session, lottery_modality)

    def _place_bet(self, session: AutomationSession, lottery_modality: LotteryModality) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        bet_page_path = self._settings.bet_page_path.format(lottery_modality=lottery_modality.value)
        self._check_redirected_page(page, self._timeout_ms, session, bet_page_path)
        self._click(page, short_timeout_ms, Selectors.COMPLETE_GAME_BUTTON)
        self._click(page, short_timeout_ms, Selectors.ADD_TO_CART_BUTTON)
        self._click(page, short_timeout_ms, Selectors.GO_TO_PAYMENT_BUTTON)
        if self._click(page, short_timeout_ms, Selectors.CONFIRM_MODAL_NO_REVIEW_CART_BUTTON):
            logger.info(
                "Foi detectada uma compra recente com o mesmo valor do carrinho nas últimas 24 horas. "
                "Não confirmar reversão do carrinho",
                extra=Operation.executed_operation(session.executed_operation),
            )

    def confirm_purchase(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._confirm_purchase, session)

    def _confirm_purchase(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(
            page, self._timeout_ms, session, self._settings.payment_method_selection_path_without_container
        )
        self._click(page, short_timeout_ms, Selectors.CONFIRM_PURCHASE_BUTTON)
        if self._click(page, short_timeout_ms, Selectors.DAILY_PURCHASE_LIMIT_ALERT_CLOSE_BUTTON):
            raise DailyPurchaseLimitError()
        if self._click(page, short_timeout_ms, Selectors.BETS_NOT_AVAILABLE_FOR_CAPTURE_ALERT_CLOSE_BUTTON):
            raise BetsNotAvailableForCaptureError()

    def confirm_payment(self) -> None:
        self._run_on_browser_thread(self._confirm_payment)

    def _confirm_payment(self) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._click(page, short_timeout_ms, Selectors.mercado_pago_card_icon(self._settings.credit_card_last_digits))
        self._click(page, short_timeout_ms, Selectors.CONTINUE_PAYMENT_BUTTON)
        self._type(page, self._timeout_ms, Selectors.SECURITY_CODE_FIELD, self._settings.credit_card_security_code)
        self._click(page, short_timeout_ms, Selectors.CONFIRM_PAYMENT_BUTTON)

    def check_bet_processing(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._check_bet_processing, session)

    def _check_bet_processing(self, session: AutomationSession) -> None:
        self._check_redirected_page(self._require_page(), self._timeout_ms, session, self._settings.bet_processing_path)

    def check_your_purchases(self, session: AutomationSession) -> str:
        return self._run_on_browser_thread(self._check_your_purchases, session)

    def _check_your_purchases(self, session: AutomationSession) -> str:
        page = self._require_page()
        purchase_number = self._wait_for_purchase_tracking(
            page,
            self._settings.bet_tracking_timeout_seconds * 1000,
            self._settings.bet_tracking_path_without_purchase,
            session,
        )
        self._click(page, self._short_timeout_ms, Selectors.TRACK_YOUR_PURCHASES_BUTTON)
        return purchase_number

    def _wait_for_purchase_tracking(self, page: Page, timeout_ms: int, path: str, session: AutomationSession) -> str:
        try:
            page.wait_for_function(
                """trackingPath => window.location.href.includes(trackingPath)""",
                arg=path,
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise PageRedirectionError(path, session.executed_operation) from exc

        return self.extract_purchase_number(page.url)

    @staticmethod
    def extract_purchase_number(url: str) -> str:
        path = urlparse(url).fragment
        return path.rstrip("/").split("/")[-1]

    def finish_bet(self, session: AutomationSession, lottery_modality: LotteryModality) -> PurchaseResult:
        return self._run_on_browser_thread(self._finish_bet, session, lottery_modality)

    def _finish_bet(self, session: AutomationSession, lottery_modality: LotteryModality) -> PurchaseResult:
        self._check_redirected_page(
            self._require_page(), self._timeout_ms, session, self._settings.bet_purchase_path_without_purchase
        )
        purchase_details = self._get_purchase_details(self._require_page(), self._timeout_ms)
        logger.info(
            "Número da compra: %s, Situação da compra: %s, Data/hora da compra: %s",
            purchase_details.number,
            purchase_details.status,
            purchase_details.bet_date.isoformat(),
            extra=Operation.executed_operation(session.executed_operation),
        )
        bets = self._get_bets(self._require_page())
        for bet in bets:
            logger.info(
                "Números da aposta: %s, Concurso da aposta: %s, Situação da aposta: %s, Valor da aposta: %s",
                bet.numbers,
                bet.draw,
                bet.status,
                BrlCurrencyFormatter.format_brl_currency(bet.amount),
                extra=Operation.executed_operation(session.executed_operation),
            )
        purchase_totals = self._get_purchase_totals(self._require_page(), self._timeout_ms)
        format_brl = BrlCurrencyFormatter.format_brl_currency

        logger.info(
            "Total da compra: %s, "
            "Total de apostas em processamento: %s, "
            "Total de apostas efetivadas: %s, "
            "Total de apostas não efetivadas: %s, "
            "Total devolvido ao meio de pagamento: %s, "
            "Total em devolução ao meio de pagamento: %s",
            format_brl(purchase_totals.total_purchase),
            format_brl(purchase_totals.total_bets_in_processing),
            format_brl(purchase_totals.total_bets_effective),
            format_brl(purchase_totals.total_bets_not_effective),
            format_brl(purchase_totals.total_refunded),
            format_brl(purchase_totals.total_in_refund),
            extra=Operation.executed_operation(session.executed_operation),
        )
        return PurchaseResult(
            lottery_modality=get_lottery_modality(lottery_modality),
            bets=[
                BetResult(
                    numbers=bet.numbers,
                    draw=bet.draw,
                    status=bet.status,
                    amount=bet.amount,
                )
                for bet in bets
            ],
            purchase_number=purchase_details.number,
            purchase_datetime=purchase_details.bet_date,
            total_purchase=purchase_totals.total_purchase,
            total_bets_effective=purchase_totals.total_bets_effective,
        )

    def _get_purchase_details(self, page: Page, timeout_ms: int) -> PurchaseDetails:
        purchase_number = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Número da Compra")
        )
        purchase_status = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Situação da Compra")
        )
        purchase_date = self._required_inner_text(page, timeout_ms, Selectors.purchase_details_value("Data da Compra"))
        purchase_time = self._required_inner_text(page, timeout_ms, Selectors.purchase_details_value("Hora da Compra"))
        return PurchaseDetails(
            number=purchase_number,
            status=purchase_status,
            date=purchase_date,
            time=purchase_time,
        )

    def _get_purchase_totals(self, page: Page, timeout_ms: int) -> PurchaseTotals:
        total_purchase = self._required_inner_text(page, timeout_ms, Selectors.purchase_totals_value("Total da Compra"))
        total_bets_in_processing = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total de Apostas em Processamento")
        )
        total_bets_effective = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total de Apostas Efetivadas")
        )
        total_bets_not_effective = self._optional_inner_text(
            page, Selectors.purchase_totals_value("Total de Apostas Não Efetivadas")
        )
        total_refunded = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total Devolvido ao Meio de Pagamento")
        )
        total_in_refund = self._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Em Devolução ao Meio de Pagamento")
        )
        return PurchaseTotals(
            total_purchase=total_purchase,
            total_bets_in_processing=total_bets_in_processing,
            total_bets_effective=total_bets_effective,
            total_bets_not_effective=total_bets_not_effective,
            total_refunded=total_refunded,
            total_in_refund=total_in_refund,
        )

    @staticmethod
    def _get_bets(page: Page) -> list[Bet]:
        rows = page.locator(Selectors.BET_TABLE_ROWS)
        bets: list[Bet] = []

        for index in range(rows.count()):
            row = rows.nth(index)
            cells = row.locator(":scope > td")

            numbers = [
                number.strip() for number in row.locator("span.margemVolante").all_inner_texts() if number.strip()
            ]

            bets.append(
                Bet(
                    numbers=numbers,
                    draw=cells.nth(1).inner_text().strip(),
                    status=cells.nth(2).inner_text().strip(),
                    amount=cells.nth(3).inner_text().strip(),
                )
            )

        return bets
