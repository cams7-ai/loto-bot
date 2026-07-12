"""Composição de dependências da aplicação."""

from __future__ import annotations

from dataclasses import dataclass

from application import RunBetFlowUseCase, SessionControlUseCase
from domain import AutomationSession, PaymentAuthorization
from infrastructure.browser import PlaywrightBrowserAutomation
from infrastructure.clients import GmailReaderClient, MailSenderClient, NotificationGateway, WhatsAppNotifyClient
from infrastructure.config import Settings, get_settings


@dataclass
class AppContainer:
    settings: Settings
    session: AutomationSession
    session_control: SessionControlUseCase
    run_bet_flow: RunBetFlowUseCase


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or get_settings()
    session = AutomationSession()
    browser = PlaywrightBrowserAutomation(resolved_settings)
    gmail = GmailReaderClient(resolved_settings)
    mail = MailSenderClient(resolved_settings)
    whatsapp = WhatsAppNotifyClient(resolved_settings)
    notifier = NotificationGateway(whatsapp=whatsapp, mail=mail, whatsapp_enabled=resolved_settings.whatsapp_enabled)
    session_control = SessionControlUseCase(session=session, browser=browser, validation_codes=gmail, notifier=notifier)
    run_bet_flow = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(resolved_settings.confirm_payment),
    )
    return AppContainer(
        settings=resolved_settings,
        session=session,
        session_control=session_control,
        run_bet_flow=run_bet_flow,
    )


container = build_container()


def get_container() -> AppContainer:
    return container
