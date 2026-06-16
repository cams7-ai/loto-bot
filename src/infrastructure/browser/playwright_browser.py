"""Adapter Playwright para automação do portal CAIXA."""

from __future__ import annotations

import re
import logging
from concurrent.futures import ThreadPoolExecutor
from secrets import token_hex
from pathlib import Path
from typing import Any

from application.ports import BrowserAutomationPort
from domain import AutomationError, AutomationSession
from infrastructure.config import Settings
from infrastructure.selectors import Selectors

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
            raise AutomationError("Não foi possível iniciar a sessão de navegador.", operation="Inicia sessão") from exc

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

    def access_lottery_portal(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._access_lottery_portal, session)

    def accept_privacy(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._accept_privacy, session)
    
    def accept_terms(self, session: AutomationSession) -> None:        
        self._run_on_browser_thread(self._accept_terms, session)

    def access_home(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._access_home, session)

    def submit_cpf(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_cpf, session)

    def request_validation_code(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._request_validation_code, session)

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        self._run_on_browser_thread(self._submit_validation_code, session, code)

    def submit_password(self, session: AutomationSession) -> None:
        self._run_on_browser_thread(self._submit_password, session)

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

    def _access_lottery_portal(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_loterias_online)

    def _accept_privacy(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_termo_de_uso)
        self._click(self._selectors.privacy_yes_button)

    def _accept_terms(self, session: AutomationSession) -> None:
#        self._goto(self._settings.url_termo_de_uso)
        self._click(self._selectors.terms_yes_button)

    def _access_home(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_home)
        self._click(self._selectors.home_access_button)

    def _submit_cpf(self, session: AutomationSession) -> None:
        self._goto(self._settings.cpf_url(str(session.state), str(session.nonce)))
        self._fill(self._selectors.cpf_field, self._settings.cpf)
        self._click(self._selectors.cpf_next_button)

    def _request_validation_code(self, session: AutomationSession) -> None:
        self._goto(self._settings.authentication_url(session.tab_id))
        self._click(self._selectors.receive_code_button)

    def _submit_validation_code(self, session: AutomationSession, code: str) -> None:
        self._goto(self._settings.authentication_url(session.tab_id))
        self._fill(self._selectors.code_field, code)
        self._click(self._selectors.code_send_button)

    def _submit_password(self, session: AutomationSession) -> None:
        self._goto(self._settings.authentication_url(session.tab_id))
        self._fill(self._selectors.password_field, self._settings.senha)
        self._click(self._selectors.password_enter_button)

    def _select_lottery_modality(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_home)
        popup = self._page.locator(self._selectors.notification_popup_close)
        if popup.count() and popup.first.is_visible():
            popup.first.click()
        self._click(self._selectors.modality_button(self._settings.modalidade_selecionada))

    def _choose_random_numbers(self, session: AutomationSession) -> None:
        self._goto(self._settings.url_escolhe_numeros_aposta)
        self._click(self._selectors.complete_game_button)

    def _add_bet_to_cart(self, session: AutomationSession) -> None:
        self._click(self._selectors.add_to_cart_button)

    def _confirm_purchase(self, session: AutomationSession) -> None:
        self._click(self._selectors.go_to_payment_button)
        self._click(self._selectors.confirm_purchase_button)

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
        self._click(self._selectors.account_button)
        self._click(self._selectors.logout_button)
        return tracking_code

    def _run_on_browser_thread(self, action, *args):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lotobot-playwright")

        return self._executor.submit(action, *args).result()

    def _goto(self, url: str) -> None:
        self._require_page().goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)

    def _click(self, selector: str) -> None:
        self._require_page().locator(selector).click()

    def _fill(self, selector: str, value: str) -> None:
        self._require_page().locator(selector).fill(value)

    def _require_page(self) -> Any:
        if self._page is None:
            raise AutomationError("A sessão de navegador está fechada.", operation="Sessão de navegador")
        return self._page

    @staticmethod
    def _tracking_code_from_url(url: str) -> str:
        match = re.search(r"/acompanhamento/(\d+)", url)
        return match.group(1) if match else ""

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
