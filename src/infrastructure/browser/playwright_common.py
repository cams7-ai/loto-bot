"" """Infraestrutura compartilhada para automação Playwright."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from playwright.sync_api import BrowserContext, Locator, Page, Playwright

from domain import (
    BROWSER_SESSION_CLOSED,
    AutomationError,
    AutomationSession,
    Operation,
    PageRedirectionError,
)
from infrastructure.config import Settings
from infrastructure.selectors import Selectors

logger = logging.getLogger(__name__)


class PlaywrightBrowserBase:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._executor: ThreadPoolExecutor | None = None

    @staticmethod
    def _optional_inner_text(page: Page, selector: Selectors | str) -> str:
        locator = page.locator(PlaywrightBrowserBase._selector_value(selector))
        if locator.count() == 0:
            return ""
        return locator.first.inner_text().strip()

    @staticmethod
    def _required_inner_text(page: Page, timeout_ms: int, selector: Selectors | str) -> str:
        locator = page.locator(PlaywrightBrowserBase._selector_value(selector)).first
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
        selector_value = PlaywrightBrowserBase._selector_value(selector)
        element = page.locator(selector_value).first
        try:
            PlaywrightBrowserBase._prepare_for_click(element, timeout_ms)
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
        selector_value = PlaywrightBrowserBase._selector_value(selector)
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
        selector_value = PlaywrightBrowserBase._selector_value(selector)
        element = page.locator(selector_value).first
        PlaywrightBrowserBase._prepare_for_click(element, timeout_ms)
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
