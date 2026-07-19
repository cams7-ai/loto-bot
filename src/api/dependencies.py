"""Composição de dependências da aplicação."""

from __future__ import annotations

from dataclasses import dataclass

from application import (
    GetPlacedBetUseCase,
    ListPlacedBetsUseCase,
    PlacedBetService,
    RunBetFlowUseCase,
    SessionControlUseCase,
)
from domain import AutomationSession, PaymentAuthorization
from infrastructure.browser import PlaywrightBrowserAutomation
from infrastructure.clients import GmailReaderClient, MailSenderClient, NotificationGateway, WhatsAppNotifyClient
from infrastructure.config import Settings, get_settings
from infrastructure.database import BeanieBetRepository, MongoDatabase


@dataclass
class AppContainer:
    settings: Settings
    session: AutomationSession
    session_control: SessionControlUseCase
    run_bet_flow: RunBetFlowUseCase
    list_placed_bets: ListPlacedBetsUseCase
    get_placed_bet: GetPlacedBetUseCase


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or get_settings()
    session = AutomationSession()
    browser = PlaywrightBrowserAutomation(resolved_settings)
    gmail = GmailReaderClient(resolved_settings)
    mail = MailSenderClient(resolved_settings)
    whatsapp = WhatsAppNotifyClient(resolved_settings)
    notifier = NotificationGateway(whatsapp=whatsapp, mail=mail, whatsapp_enabled=resolved_settings.whatsapp_enabled)
    session_control = SessionControlUseCase(session=session, browser=browser, validation_codes=gmail, notifier=notifier)
    database = MongoDatabase(uri=resolved_settings.mongodb_uri, database_name=resolved_settings.mongodb_database)
    bet_repository = BeanieBetRepository(database=database)
    list_placed_bets = ListPlacedBetsUseCase(repository=bet_repository)
    get_placed_bet = GetPlacedBetUseCase(repository=bet_repository)
    bet_persistence = (
        PlacedBetService(
            repository=bet_repository,
            selected_lottery_modality=resolved_settings.selected_lottery_modality,
        )
        if resolved_settings.mongodb_enabled
        else None
    )
    run_bet_flow = RunBetFlowUseCase(
        session=session,
        browser=browser,
        notifier=notifier,
        payment_authorization=PaymentAuthorization(resolved_settings.confirm_payment),
        bet_persistence=bet_persistence,
        selected_lottery_modality=resolved_settings.selected_lottery_modality,
    )
    return AppContainer(
        settings=resolved_settings,
        session=session,
        session_control=session_control,
        run_bet_flow=run_bet_flow,
        list_placed_bets=list_placed_bets,
        get_placed_bet=get_placed_bet,
    )


container = build_container()


def get_container() -> AppContainer:
    return container
