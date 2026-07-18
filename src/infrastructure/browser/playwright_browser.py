"""Adapter Playwright para automação do portal CAIXA."""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from application import BrowserAutomationPort
from infrastructure.browser.run_bet_flow_browser import RunBetFlowBrowserMixin
from infrastructure.browser.session_control_browser import SessionControlBrowserMixin

__all__ = ["PlaywrightBrowserAutomation", "sync_playwright"]


class PlaywrightBrowserAutomation(SessionControlBrowserMixin, RunBetFlowBrowserMixin, BrowserAutomationPort):
    pass
