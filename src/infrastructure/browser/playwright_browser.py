"""Adapter Playwright para automação do portal CAIXA"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from secrets import token_hex
from time import monotonic
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import (
    BrowserContext,
    Locator,
    Page,
    Playwright,
    sync_playwright,
)

from application import BrowserAutomationPort
from application.dto import BetResult, PurchaseResult
from domain import (
    BROWSER_SESSION_CLOSED,
    BROWSER_SESSION_START_FAILED,
    CAIXA_AUTHENTICATION_FORBIDDEN,
    LOTTERY_MODALITY_NOT_FOUND,
    AutomationError,
    AutomationSession,
    BetTemporarilyDisabledError,
    DailyPurchaseLimitError,
    IndividualBetRegistrationClosedError,
    InvalidCPFError,
    InvalidPasswordError,
    LotteryModality,
    Operation,
    PageRedirectionError,
)
from infrastructure.browser.portal_data import Bet, PortalDataFormatter, PurchaseDetails, PurchaseTotals
from infrastructure.config import Settings
from infrastructure.selectors import LotteryModalityBuilder, Selectors

logger = logging.getLogger(__name__)


class PlaywrightBrowserAutomation(BrowserAutomationPort):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._executor: ThreadPoolExecutor | None = None

    def start(self, session: AutomationSession) -> str:
        try:
            return self._run_on_browser_thread(self._start, session)
        except Exception:
            if self._executor is not None:
                self._executor.shutdown(wait=True)
                self._executor = None
            raise

    def _start(self, session: AutomationSession) -> str:
        try:
            self._ensure_profile_dir(self._settings.browser_profile_dir)
            self._playwright = sync_playwright().start()
            viewport = None
            if self._settings.browser_headless:
                viewport = {"width": 1280, "height": 900}

            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._settings.browser_profile_dir),
                headless=self._settings.browser_headless,
                viewport=viewport,
                args=self._launch_args(self._settings.browser_headless),
                user_agent=self._user_agent(),
                locale="pt-BR",
            )
            self._context.set_default_timeout(self._timeout_ms)
            self._add_init_script(self._context)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            return token_hex(4)
        except Exception as exc:
            self._stop()
            logging.debug(
                "Falha ao iniciar a sessão de navegador; encerrando contexto e Playwright",
                extra=Operation.executed_operation(session.executed_operation),
            )
            raise AutomationError(BROWSER_SESSION_START_FAILED, operation=session.executed_operation) from exc

    @staticmethod
    def _ensure_profile_dir(profile_dir: Path) -> None:
        profile_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _launch_args(browser_headless: bool) -> list[str]:
        if browser_headless:
            return [
                "--disable-infobars",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,900",
            ]

        return ["--start-maximized"]

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )

    @staticmethod
    def _add_init_script(context: BrowserContext | None) -> None:
        if context is None:
            return

        try:
            context.add_init_script(
                """
                try {
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = window.chrome || {};
                    Object.defineProperty(navigator, 'language', { get: () => 'en-US' });
                } catch (e) {
                    // ignore
                }
                """
            )
        except Exception:
            logger.debug("Não foi possível injetar init script no contexto")

    def stop(self) -> None:
        if self._executor is None:
            self._stop()
            return

        try:
            self._run_on_browser_thread(self._stop)
        finally:
            self._executor.shutdown(wait=True)
            self._executor = None

    def _stop(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._context = None
        self._page = None
        self._playwright = None

    def access_home(self) -> None:
        self._run_on_browser_thread(self._access_home, True)

    def access_authenticated_home(self) -> None:
        self._run_on_browser_thread(self._access_home, False)

    def _access_home(self, click_login_button: bool) -> None:
        page = self._require_page()
        self._goto(page, self._timeout_ms, self._settings.home_url)
        if click_login_button:
            self._click(page, self._short_timeout_ms, Selectors.LOGGED_OFF_LOGIN_BUTTON)

    def is_authenticated(self) -> bool:
        return self._run_on_browser_thread(self._is_authenticated, False)

    def is_already_authenticated(self) -> bool:
        return self._run_on_browser_thread(self._is_authenticated, True)

    def _is_authenticated(self, click_login_button: bool) -> bool:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        if not click_login_button:
            return self._click_login_button(page, short_timeout_ms)

        if self._disable_notification(page, short_timeout_ms):
            logger.info("A notificação foi desabilitada")

        if self._accept_terms_of_use(page, short_timeout_ms):
            logger.info("Os termos de uso foram aceitos")

        if self._click(page, short_timeout_ms, Selectors.LOGGED_OFF_LOGIN_BUTTON):
            logger.debug("O botão de login do usuário deslogado foi clicado")

        return self._click_login_button(page, short_timeout_ms)

    @staticmethod
    def _click_login_button(page: Page, timeout_ms: int) -> bool:
        selector = Selectors.LOGGED_IN_LOGIN_BUTTON
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            logger.debug(
                "A sessão não está autenticada ou o elemento de login autenticado não ficou visível "
                "dentro do tempo limite de %d ms: %s",
                timeout_ms,
                selector,
            )
        return False

    @staticmethod
    def _disable_notification(page: Page, timeout_ms: int) -> bool:
        if PlaywrightBrowserAutomation._click(page, timeout_ms, Selectors.DO_NOT_SHOW_NOTIFICATION_CHECKBOX):
            return PlaywrightBrowserAutomation._click(page, timeout_ms, Selectors.CLOSE_NOTIFICATION_BUTTON)
        return False

    @staticmethod
    def _accept_terms_of_use(page: Page, timeout_ms: int) -> bool:
        if PlaywrightBrowserAutomation._click(page, timeout_ms, Selectors.TERMS_OF_USE_CHECKBOX):
            return PlaywrightBrowserAutomation._click(page, timeout_ms, Selectors.ACCEPT_TERMS_OF_USE_BUTTON)
        return False

    def accept_terms(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._accept_terms, session)

    def _accept_terms(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.terms_of_use_path)
        self._accept_privacy(page, short_timeout_ms)
        self._click(page, short_timeout_ms, Selectors.TERMS_YES_BUTTON)

    @staticmethod
    def _accept_privacy(page: Page, timeout_ms: int) -> None:
        PlaywrightBrowserAutomation._click(page, timeout_ms, Selectors.PRIVACY_YES_BUTTON)

    def submit_cpf(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_cpf, session)

    def _submit_cpf(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.openid_connect_auth_path)
        self._fill(page, Selectors.CPF_FIELD, self._settings.bettor_cpf)
        self._click(page, short_timeout_ms, Selectors.CPF_NEXT_BUTTON)
        self._raise_if_invalid_cpf(page, short_timeout_ms)

    @staticmethod
    def _raise_if_invalid_cpf(page: Page, timeout_ms: int) -> None:
        try:
            page.locator(Selectors.CPF_INVALID_ALERT).first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        except Exception:
            return

        raise InvalidCPFError()

    def is_valid_cpf(self) -> bool:
        return self._run_on_browser_thread(self._is_valid_cpf)

    def _is_valid_cpf(self) -> bool:
        timeout_ms = self._timeout_ms
        try:
            self._require_page().locator(Selectors.RECEIVE_CODE_BUTTON).first.wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:
            logger.debug(
                "O CPF não é válido ou o botão de receber código não ficou visível dentro do tempo limite de %d ms: %s",
                timeout_ms,
                Selectors.RECEIVE_CODE_BUTTON,
            )
        return False

    def validation_code_lookup_lead(self) -> int:
        return self._settings.validation_code_lookup_lead_seconds * 1000

    def request_validation_code(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._request_validation_code, session)

    def _request_validation_code(self, session: AutomationSession) -> None:
        page = self._require_page()
        self._check_redirected_page(
            page, self._timeout_ms, session, self._settings.authenticate_path, self._extract_execution_and_tab_params
        )
        self._raise_if_forbidden(page, session.executed_operation)
        self._click(page, self._short_timeout_ms, Selectors.RECEIVE_CODE_BUTTON)

    @staticmethod
    def _extract_execution_and_tab_params(url: str, session: AutomationSession) -> None:
        params = parse_qs(urlparse(url).query)

        execution_id = PlaywrightBrowserAutomation._first_query_param(params, "execution")
        tab_id = PlaywrightBrowserAutomation._first_query_param(params, "tab_id")

        if execution_id:
            session.execution_id = execution_id

        if tab_id:
            session.tab_id = tab_id

    @staticmethod
    def _first_query_param(params: dict[str, list[str]], name: str) -> str:
        values = params.get(name) or []
        return values[0] if values else ""

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        self._run_on_browser_thread(self._submit_validation_code, session, code)

    def _submit_validation_code(self, session: AutomationSession, code: str) -> None:
        page = self._require_page()
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.authenticate_path)
        self._fill(page, Selectors.CODE_FIELD, code)
        self._click(page, self._short_timeout_ms, Selectors.CODE_SEND_BUTTON)

    def submit_password(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_password, session)

    def _submit_password(self, session: AutomationSession) -> None:
        page = self._require_page()
        timeout_ms = self._timeout_ms
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, timeout_ms, session, self._settings.authenticate_path)
        self._fill(page, Selectors.PASSWORD_FIELD, self._settings.bettor_password)
        self._click(page, short_timeout_ms, Selectors.PASSWORD_ENTER_BUTTON)
        self._raise_if_invalid_password(page, timeout_ms, short_timeout_ms)

    @staticmethod
    def _raise_if_invalid_password(page: Page, timeout_ms: int, short_timeout_ms: int) -> None:
        try:
            page.locator(Selectors.PASSWORD_INVALID_ALERT).first.wait_for(
                state="visible",
                timeout=short_timeout_ms,
            )
        except Exception:
            pass
        else:
            raise InvalidPasswordError()

        try:
            page.locator(Selectors.PASSWORD_FIELD).first.wait_for(
                state="hidden",
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise InvalidPasswordError() from exc

    def clear_shopping_cart(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._clear_shopping_cart_if_needed, session)

    def _clear_shopping_cart_if_needed(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        if self._shopping_cart_items_count(page) > 0:
            self._click(page, short_timeout_ms, Selectors.SHOPPING_CART_BUTTON)
            self._clear_shopping_cart(
                page, self._timeout_ms, short_timeout_ms, self._settings.shopping_cart_path, session
            )

    @staticmethod
    def _shopping_cart_items_count(page: Page) -> int:
        text = page.locator(Selectors.SHOPPING_CART_BUTTON).first.text_content()
        match = re.search(r"\d+", text or "")
        return int(match.group()) if match else 0

    @staticmethod
    def _clear_shopping_cart(
        page: Page, timeout_ms: int, short_timeout_ms: int, path: str, session: AutomationSession
    ) -> None:
        PlaywrightBrowserAutomation._check_redirected_page(page, timeout_ms, session, path)
        PlaywrightBrowserAutomation._click(page, short_timeout_ms, Selectors.CLEAR_CART_BUTTON)
        PlaywrightBrowserAutomation._click(page, short_timeout_ms, Selectors.CONFIRM_CLEAR_CART_BUTTON)

    def select_lottery_modality(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._select_lottery_modality, session)

    def _select_lottery_modality(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.home_path)
        lottery_modality = self._settings.selected_lottery_modality
        selector = Selectors.modality_button(lottery_modality)
        if selector is None:
            raise AutomationError(
                LOTTERY_MODALITY_NOT_FOUND.format(modality=lottery_modality),
                operation=Operation.SELECT_LOTTERY_MODALITY,
            )

        if not self._click(page, short_timeout_ms, selector):
            selector = Selectors.disabled_modality_button(lottery_modality)
            if selector is not None and self._click(page, short_timeout_ms, selector):
                raise BetTemporarilyDisabledError(lottery_modality)

        if self._click(page, short_timeout_ms, Selectors.CLOSE_BET_REGISTRATION_ALERT_BUTTON):
            raise IndividualBetRegistrationClosedError()

    def place_bet(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._place_bet, session)

    def _place_bet(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.bet_page_path_with_modality)
        self._click(page, short_timeout_ms, Selectors.COMPLETE_GAME_BUTTON)  # Complete o Jogo
        self._click(page, short_timeout_ms, Selectors.ADD_TO_CART_BUTTON)  # Colocar no Carrinho
        self._click(page, short_timeout_ms, Selectors.GO_TO_PAYMENT_BUTTON)  # Ir para pagamento
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
        self._click(page, short_timeout_ms, Selectors.CONFIRM_PURCHASE_BUTTON)  # Confirmar Pagamento
        if self._click(page, short_timeout_ms, Selectors.DAILY_PURCHASE_LIMIT_ALERT_CLOSE_BUTTON):
            raise DailyPurchaseLimitError()

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

    def check_your_purchases(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._check_your_purchases, session)

    def _check_your_purchases(self, session: AutomationSession) -> None:
        page = self._require_page()
        self._wait_for_purchase_tracking(
            page,
            self._settings.bet_tracking_timeout_seconds * 1000,
            self._settings.bet_tracking_path_without_purchase,
            session,
        )
        self._click(page, self._short_timeout_ms, Selectors.TRACK_YOUR_PURCHASES_BUTTON)

    @staticmethod
    def _wait_for_purchase_tracking(page: Page, timeout_ms: int, path: str, session: AutomationSession) -> None:
        try:
            page.wait_for_function(
                """trackingPath => window.location.href.includes(trackingPath)""",
                arg=path,
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise PageRedirectionError(path, session.executed_operation) from exc

        PlaywrightBrowserAutomation._extract_purchase(page.url, session)

    @staticmethod
    def _extract_purchase(url: str, session: AutomationSession) -> None:
        purchase_number = PlaywrightBrowserAutomation.extract_purchase_number(url)

        if purchase_number:
            session.purchase_number = purchase_number

    @staticmethod
    def extract_purchase_number(url: str) -> str:
        path = urlparse(url).fragment
        return path.rstrip("/").split("/")[-1]

    def finish_bet(self, session: AutomationSession) -> PurchaseResult:
        return self._run_on_browser_thread(self._finish_bet, session)

    def _finish_bet(self, session: AutomationSession) -> PurchaseResult:
        self._check_redirected_page(
            self._require_page(), self._timeout_ms, session, self._settings.bet_purchase_path_without_purchase
        )
        purchase_details = self._get_purchase_details(self._require_page(), self._timeout_ms)
        logger.info(
            f"Número da compra: {purchase_details.number}, "
            f"Situação da compra: {purchase_details.status}, "
            f"Data/hora da compra: {purchase_details.datetime.isoformat()}",
            extra=Operation.executed_operation(session.executed_operation),
        )
        bets = self._get_bets(self._require_page())
        for bet in bets:
            logger.info(
                f"Números da aposta: {bet.numbers}, "
                f"Concurso da aposta: {bet.draw}, "
                f"Situação da aposta: {bet.status}, "
                f"Valor da aposta: {PortalDataFormatter.format_brl_currency(bet.amount)}",
                extra=Operation.executed_operation(session.executed_operation),
            )
        purchase_totals = self._get_purchase_totals(self._require_page(), self._timeout_ms)
        format_brl = PortalDataFormatter.format_brl_currency

        logger.info(
            f"Total da compra: {format_brl(purchase_totals.total_purchase)}, "
            f"Total de apostas em processamento: {format_brl(purchase_totals.total_bets_in_processing)}, "
            f"Total de apostas efetivadas: {format_brl(purchase_totals.total_bets_effective)}, "
            f"Total de apostas não efetivadas: {format_brl(purchase_totals.total_bets_not_effective)}, "
            f"Total devolvido ao meio de pagamento: {format_brl(purchase_totals.total_refunded)}, "
            f"Total em devolução ao meio de pagamento: {format_brl(purchase_totals.total_in_refund)}",
            extra=Operation.executed_operation(session.executed_operation),
        )
        return PurchaseResult(
            lottery_modality=LotteryModalityBuilder.get_lottery_modality(
                LotteryModality.from_string(self._settings.selected_lottery_modality)
            ),
            bets=[
                BetResult(
                    numbers=bet.numbers,
                    draw=bet.draw,
                    status=bet.status,
                    amount=bet.amount,
                )
                for bet in bets
            ],
            purchase_details_number=purchase_details.number,
            purchase_details_datetime=purchase_details.datetime,
            total_purchase=purchase_totals.total_purchase,
            total_bets_effective=purchase_totals.total_bets_effective,
        )

    @staticmethod
    def _get_purchase_details(page: Page, timeout_ms: int) -> PurchaseDetails:
        purchase_number = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Número da Compra")
        )
        purchase_status = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Situação da Compra")
        )
        purchase_date = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Data da Compra")
        )
        purchase_time = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_details_value("Hora da Compra")
        )
        return PurchaseDetails(
            number=purchase_number,
            status=purchase_status,
            date=purchase_date,
            time=purchase_time,
        )

    @staticmethod
    def _get_purchase_totals(page: Page, timeout_ms: int) -> PurchaseTotals:
        total_purchase = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total da Compra")
        )
        total_bets_in_processing = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total de Apostas em Processamento")
        )
        total_bets_effective = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total de Apostas Efetivadas")
        )
        total_bets_not_effective = PlaywrightBrowserAutomation._optional_inner_text(
            page, Selectors.purchase_totals_value("Total de Apostas Não Efetivadas")
        )
        total_refunded = PlaywrightBrowserAutomation._required_inner_text(
            page, timeout_ms, Selectors.purchase_totals_value("Total Devolvido ao Meio de Pagamento")
        )
        total_in_refund = PlaywrightBrowserAutomation._required_inner_text(
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

    @staticmethod
    def _optional_inner_text(page: Page, selector: Selectors | str) -> str:
        locator = page.locator(PlaywrightBrowserAutomation._selector_value(selector))
        if locator.count() == 0:
            return ""
        return locator.first.inner_text().strip()

    @staticmethod
    def _required_inner_text(page: Page, timeout_ms: int, selector: Selectors | str) -> str:
        locator = page.locator(PlaywrightBrowserAutomation._selector_value(selector)).first
        locator.wait_for(state="visible", timeout=timeout_ms)

        deadline = monotonic() + (timeout_ms / 1000)
        text = ""
        while monotonic() < deadline:
            text = locator.inner_text().strip()
            if text:
                return text
            page.wait_for_timeout(100)

        return text

    @staticmethod
    def _click(page: Page, timeout_ms: int, selector: Selectors | str) -> bool:
        selector_value = PlaywrightBrowserAutomation._selector_value(selector)
        element = page.locator(selector_value).first
        try:
            PlaywrightBrowserAutomation._prepare_for_click(element, timeout_ms)
            element.click()
            return True
        except Exception:
            logger.debug(
                "Clique ignorado porque o elemento não foi encontrado ou não ficou visível "
                "dentro do tempo limite de %d ms: %s",
                timeout_ms,
                selector_value,
            )
        return False

    @staticmethod
    def _fill(page: Page, selector: Selectors | str, value: str) -> bool:
        selector_value = PlaywrightBrowserAutomation._selector_value(selector)
        element = page.locator(selector_value)
        try:
            element.fill(value)
            return True
        except Exception:
            logger.debug(
                "Preenchimento ignorado porque o elemento não foi encontrado: %s",
                selector_value,
            )
        return False

    @staticmethod
    def _type(page: Page, timeout_ms: int, selector: Selectors | str, value: str) -> bool:
        selector_value = PlaywrightBrowserAutomation._selector_value(selector)
        element = page.locator(selector_value).first
        PlaywrightBrowserAutomation._prepare_for_click(element, timeout_ms)
        element.click()
        element.fill("")

        press_sequentially = getattr(element, "press_sequentially", None)
        if press_sequentially is not None:
            press_sequentially(value, delay=50)
            return True

        element.type(value, delay=50)
        return True

    @staticmethod
    def _prepare_for_click(element: Locator, timeout_ms: int) -> None:
        element.wait_for(state="visible", timeout=timeout_ms)
        element.scroll_into_view_if_needed(timeout=timeout_ms)

    @staticmethod
    def _selector_value(selector: Selectors | str) -> str:
        if isinstance(selector, Selectors):
            return selector.value
        return selector

    @staticmethod
    def _raise_if_forbidden(page: Page, operation: Operation) -> None:
        title = page.locator("h1.error-header__title")
        if title.count() > 0 and title.first.inner_text().strip().lower() == "forbidden":
            raise AutomationError(CAIXA_AUTHENTICATION_FORBIDDEN, operation=operation)

    def _require_page(self) -> Page:
        if self._page is None:
            raise AutomationError(BROWSER_SESSION_CLOSED, operation=Operation.END_SESSION)
        return self._page

    @staticmethod
    def _check_redirected_page(
        page: Page,
        timeout_ms: int,
        session: AutomationSession,
        path: str,
        extract_params: Callable[[str, AutomationSession], None] | None = None,
    ) -> None:

        try:
            page.wait_for_url(
                re.compile(rf".*{path}.*"),
                timeout=timeout_ms,
            )
        except Exception as exc:
            raise PageRedirectionError(path, session.executed_operation) from exc

        if extract_params is not None:
            extract_params(page.url, session)

    @staticmethod
    def _goto(page: Page, timeout_ms: int, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    def _run_on_browser_thread(self, action, *args):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-playwright")

        return self._executor.submit(action, *args).result()

    @property
    def _timeout_ms(self) -> int:
        return self._settings.browser_timeout_seconds * 1000

    @property
    def _short_timeout_ms(self) -> int:
        return min(2000, self._timeout_ms)
