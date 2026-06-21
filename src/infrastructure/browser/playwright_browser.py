"""Adapter Playwright para automação do portal CAIXA."""

from __future__ import annotations

import re
import logging
from concurrent.futures import ThreadPoolExecutor
from secrets import token_hex
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from application.ports import BrowserAutomationPort
from domain import (
    Operation, 
    AutomationSession, 
    AutomationError,
)
from infrastructure import Settings, Selectors

logger = logging.getLogger(__name__)

class PlaywrightBrowserAutomation(BrowserAutomationPort):
    def __init__(self, settings: Settings, selectors: Selectors | None = None) -> None:
        self._settings = settings
        self._selectors = selectors or Selectors()
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
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
            from playwright.sync_api import sync_playwright

            self._ensure_profile_dir(self._settings.browser_profile_dir)
            self._playwright = sync_playwright().start()
            viewport = None
            if self._settings.browser_headless:
                viewport = {"width": 1280, "height": 900}

            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._settings.browser_profile_dir),
                headless=self._settings.browser_headless,
                viewport=viewport,
                args=self._launch_args(),
                user_agent=self._user_agent(),
                locale="pt-BR",
            )
            self._context.set_default_timeout(self._timeout_ms)
            self._add_init_script()
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            return token_hex(4)
        except Exception as exc:
            self._stop()
            raise AutomationError("Não foi possível iniciar a sessão de navegador.", operation=Operation.START_SESSION) from exc

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

    def access_home(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._access_home, session)

    def access_lottery_portal(self, session: AutomationSession) -> None:
        self.access_home(session)

    def is_authenticated(self, click_login_button: bool | AutomationSession) -> bool:
        return self._run_on_browser_thread(self._is_authenticated, click_login_button)

    def accept_terms(self, session: AutomationSession) -> None:       
        self._run_on_browser_thread(self._accept_terms, session)

    def submit_cpf(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_cpf, session)

    def request_validation_code(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._request_validation_code, session)

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        self._run_on_browser_thread(self._submit_validation_code, session, code)

    def submit_password(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_password, session)

    def disable_notification(self) -> None:
        self._run_on_browser_thread(self._disable_notification)

    def select_lottery_modality(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._select_lottery_modality, session)

    def choose_random_numbers(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._choose_random_numbers, session)

    def add_bet_to_cart(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._add_bet_to_cart, session)

    def confirm_purchase(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._confirm_purchase, session)

    def select_payment_method(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._select_payment_method, session)

    def confirm_payment(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._confirm_payment, session)

    def finish_bet(self, session: AutomationSession) -> str:
        return self._run_on_browser_thread(self._finish_bet, session)

    def _access_home(self, session: AutomationSession) -> None:
        self._access_home_page(session)
        self._click_if_exists(self._selectors.logged_off_login_button, True)

    def _access_home_page(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_home)

    def _is_authenticated(self, click_login_button: bool | AutomationSession) -> bool:
        if isinstance(click_login_button, AutomationSession):
            return self._is_authenticated_from_home()

        if not click_login_button or self._click_if_exists(self._selectors.logged_off_login_button, True):
            timeout_ms = self._timeout_ms
            try:
                self._require_page().locator(self._selectors.logged_in_login_button).first.wait_for(state="visible", timeout=timeout_ms)
                return True
            except Exception:
                logger.debug(
                    "A sessão não está autenticada ou o elemento de login autenticado não ficou visível dentro do tempo limite de %d ms: %s",
                    timeout_ms,
                    self._selectors.logged_in_login_button,
                )
        return False

    def _is_authenticated_from_home(self) -> bool:
        timeout_ms = self._timeout_ms
        try:
            self._require_page().locator(self._selectors.close_notification_button).first.wait_for(state="visible", timeout=timeout_ms)
            self._require_page().locator(self._selectors.logged_in_user_notifications_link).first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False

    def _accept_terms(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_termo_de_uso)
        self._accept_privacy()
        self._click(self._selectors.terms_yes_button)

    def _accept_privacy(self) -> None:
        self._click_if_exists(self._selectors.privacy_yes_button, True)

    def _submit_cpf(self, session: AutomationSession) -> None:
        self._goto(self._settings.cpf_url(str(session.state), str(session.nonce)))
        self._fill(self._selectors.cpf_field, self._settings.cpf)
        self._click(self._selectors.cpf_next_button)
        self._sync_auth_session_from_current_url(session)

    def _request_validation_code(self, session: AutomationSession) -> None:
        self._raise_if_forbidden(Operation.REQUEST_VALIDATION_CODE)
        self._click(self._selectors.receive_code_button)

    def _submit_validation_code(self, session: AutomationSession, code: str) -> None:
        self._raise_if_forbidden(Operation.SUBMIT_VALIDATION_CODE)
        self._fill(self._selectors.code_field, code)
        self._click(self._selectors.code_send_button)

    def _submit_password(self, session: AutomationSession) -> None:
        self._raise_if_forbidden(Operation.SUBMIT_PASSWORD)
        self._fill(self._selectors.password_field, self._settings.senha)
        self._click(self._selectors.password_enter_button)

    def _disable_notification(self) -> None:
        if self._click_if_exists(self._selectors.do_not_show_notification_checkbox, True):
            self._click_if_exists(self._selectors.close_notification_button, True)

    def _select_lottery_modality(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_home)
        self._accept_privacy()
        #self._click_if_exists(self._selectors.notification_popup_close, True)
        self._click(self._selectors.modality_button(self._settings.modalidade_selecionada))
        if self._click_if_exists(self._selectors.close_bet_registration_alert_button, True):
            logger.debug("Alerta de registro de apostas individuais fechado")

    def _choose_random_numbers(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_escolhe_numeros_aposta)
        self._click(self._selectors.complete_game_button)

    def _add_bet_to_cart(self, session: AutomationSession) -> None:
        self._click(self._selectors.add_to_cart_button)

    def _confirm_purchase(self, session: AutomationSession) -> None:
        try:
            page = self._require_page()
            payment_button = page.locator(self._selectors.go_to_payment_button).first
            confirmation_button = page.locator(self._selectors.confirm_purchase_button).first
            timeout_ms = self._timeout_ms

            for attempt in range(2):
                payment_button.click(no_wait_after=True)
                try:
                    confirmation_button.wait_for(state="visible", timeout=timeout_ms)
                    confirmation_button.click()
                    return
                except Exception:
                    if attempt == 1:
                        raise
                    page.wait_for_timeout(500)
        except Exception:
            page = self._require_page()
            screenshot_path = self._settings.browser_profile_dir.parent / "artefatos" / "confirm-purchase-error.png"
            try:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                logger.exception("Não foi possível capturar screenshot da falha na confirmação da compra")
                logger.error(
                    "Falha ao confirmar compra; url=%s screenshot=%s",
                    page.url,
                    screenshot_path,
                    extra=Operation.executed_operation(Operation.CONFIRM_PURCHASE),
                )
            raise

    def _select_payment_method(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_seleciona_pix_ou_cartao)
        self._click(self._selectors.card_selector(self._settings.final_cartao_credito))

    def _confirm_payment(self, session: AutomationSession) -> None:
        self._click(self._selectors.continue_payment_button)
        self._fill(self._selectors.security_code_field, self._settings.codigo_de_seguranca_do_cartao_de_credito)
        self._click(self._selectors.confirm_payment_button)

    def _finish_bet(self, session: AutomationSession) -> str:
        self._goto(self._settings.url_finaliza_a_aposta_processando)
        self._page.wait_for_selector(self._selectors.finished_order_text)
        tracking_code = self._tracking_code_from_url(self._page.url)
        self._click(self._selectors.logged_in_login_button)
        self._click(self._selectors.logout_button)
        return tracking_code

    def _run_on_browser_thread(self, action, *args):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-playwright")

        return self._executor.submit(action, *args).result()

    def _goto(self, url: str) -> None:
        self._require_page().goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)

    def _click(self, selector: str) -> bool:
        return self._click_if_exists(selector, False)

    def _click_if_exists(self, selector: str, check_selector: bool) -> bool:
        element = self._require_page().locator(selector)
        if check_selector:
            timeout_ms = self._timeout_ms
            try:
                element.wait_for(state="visible", timeout=timeout_ms)
                element.click()
                return True
            except Exception:
                logger.debug(
                    "Clique ignorado porque o elemento não foi encontrado ou não ficou visível dentro do tempo limite de %d ms: %s",
                    timeout_ms,
                    selector,
                )
            return False

        element.click()
        return True



    def _fill(self, selector: str, value: str) -> bool:
        return self._fill_if_exists(selector, value, False)

    def _fill_if_exists(self, selector: str, value: str, check_selector: bool) -> bool:
        element = self._require_page().locator(selector)
        if check_selector:
            timeout_ms = self._timeout_ms
            try:
                element.wait_for(state="visible", timeout=timeout_ms)
                element.fill(value)
                return True
            except Exception:
                logger.debug(
                    "Preenchimento ignorado porque o elemento não foi encontrado ou não ficou visível dentro do tempo limite de %d ms: %s",
                    timeout_ms,
                    selector,
                )
            return False

        element.fill(value)
        return True

    def _sync_auth_session_from_current_url(self, session: AutomationSession) -> None:
        page = self._require_page()
        try:
            page.wait_for_url(re.compile(r".*/login-actions/authenticate.*"), timeout=self._timeout_ms)
        except Exception:
            logger.debug("Não foi possível aguardar a URL de autenticação do Login CAIXA")

        params = parse_qs(urlparse(page.url).query)
        execution = self._first_query_param(params, "execution")
        tab_id = self._first_query_param(params, "tab_id")
        if execution:
            session.execution = execution
        if tab_id:
            session.tab_id = tab_id

#    def _authentication_url(self, session: AutomationSession, operation: Operation) -> str:
#        execution = session.execution or self._settings.execution
#        if not execution or execution == "<EXECUTION_ID_DA_SESSAO>":
#            raise AutomationError(
#                "Não foi possível continuar o login sem o execution dinâmico da sessão.",
#                operation=operation,
#            )
#        return self._settings.authentication_url(session.tab_id, execution)

    def _raise_if_forbidden(self, operation: Operation) -> None:
        page = self._require_page()
        title = page.locator("h1.error-header__title")
        if title.count() > 0 and title.first.inner_text().strip().lower() == "forbidden":
            raise AutomationError(
                "Login CAIXA retornou Forbidden ao continuar a autenticação. "
                "A sessão atual foi bloqueada pelo serviço; reinicie o navegador/perfil e tente novamente.",
                operation=operation,
            )

    def _require_page(self) -> Any:
        if self._page is None:
            raise AutomationError("A sessão de navegador está fechada.", operation=Operation.END_SESSION)
        return self._page

    @staticmethod
    def _tracking_code_from_url(url: str) -> str:
        match = re.search(r"/acompanhamento/(\d+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _first_query_param(params: dict[str, list[str]], name: str) -> str:
        values = params.get(name) or []
        return values[0] if values else ""

    @property
    def _timeout_ms(self) -> int:
        return self._settings.browser_timeout_seconds * 1000

    def _add_init_script(self) -> None:
        if self._context is None:
            return

        try:
            self._context.add_init_script(
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

    def _launch_args(self) -> list[str]:
        if self._settings.browser_headless:
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
    def _ensure_profile_dir(profile_dir: Path) -> None:
        profile_dir.mkdir(parents=True, exist_ok=True)
