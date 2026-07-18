"""Operações Playwright usadas pelo controle de sessão."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from domain import (
    BROWSER_SESSION_START_FAILED,
    CAIXA_AUTHENTICATION_FORBIDDEN,
    AutomationError,
    AutomationSession,
    InvalidCPFError,
    InvalidPasswordError,
    Operation,
)
from infrastructure.browser.playwright_common import PlaywrightBrowserBase
from infrastructure.selectors import Selectors

logger = logging.getLogger(__name__)


class SessionControlBrowserMixin(PlaywrightBrowserBase):
    def start(self, session: AutomationSession) -> None:
        try:
            self._run_on_browser_thread(self._start, session)
        except Exception:
            if self._executor is not None:
                self._executor.shutdown(wait=True)
                self._executor = None
            raise

    def _start(self, session: AutomationSession) -> None:
        try:
            from infrastructure.browser import playwright_browser

            self._ensure_profile_dir(self._settings.browser_profile_dir)
            self._playwright = playwright_browser.sync_playwright().start()
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

    def _disable_notification(self, page: Page, timeout_ms: int) -> bool:
        if self._click(page, timeout_ms, Selectors.DO_NOT_SHOW_NOTIFICATION_CHECKBOX):
            return self._click(page, timeout_ms, Selectors.CLOSE_NOTIFICATION_BUTTON)
        return False

    def _accept_terms_of_use(self, page: Page, timeout_ms: int) -> bool:
        if self._click(page, timeout_ms, Selectors.TERMS_OF_USE_CHECKBOX):
            return self._click(page, timeout_ms, Selectors.ACCEPT_TERMS_OF_USE_BUTTON)
        return False

    def accept_terms(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._accept_terms, session)

    def _accept_terms(self, session: AutomationSession) -> None:
        page = self._require_page()
        short_timeout_ms = self._short_timeout_ms
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.terms_of_use_path)
        self._accept_privacy(page, short_timeout_ms)
        self._click(page, short_timeout_ms, Selectors.TERMS_YES_BUTTON)

    def _accept_privacy(self, page: Page, timeout_ms: int) -> None:
        self._click(page, timeout_ms, Selectors.PRIVACY_YES_BUTTON)

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
        self._check_redirected_page(page, self._timeout_ms, session, self._settings.authenticate_path)
        self._raise_if_forbidden(page, session.executed_operation)
        self._click(page, self._short_timeout_ms, Selectors.RECEIVE_CODE_BUTTON)

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

    def _clear_shopping_cart(
        self, page: Page, timeout_ms: int, short_timeout_ms: int, path: str, session: AutomationSession
    ) -> None:
        self._check_redirected_page(page, timeout_ms, session, path)
        self._click(page, short_timeout_ms, Selectors.CLEAR_CART_BUTTON)
        self._click(page, short_timeout_ms, Selectors.CONFIRM_CLEAR_CART_BUTTON)

    @staticmethod
    def _raise_if_forbidden(page: Page, operation: Operation) -> None:
        title = page.locator("h1.error-header__title")
        if title.count() > 0 and title.first.inner_text().strip().lower() == "forbidden":
            raise AutomationError(CAIXA_AUTHENTICATION_FORBIDDEN, operation=operation)
